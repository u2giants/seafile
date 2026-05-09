#!/usr/bin/env python3
"""
seaf-entrypoint.py

Staging wrapper for flrnnc/seafile-client. Populates /library from /source,
optionally limited to files modified within SEAF_INGEST_DAYS days, then
hands off to the upstream entrypoint at /home/seafile/entrypoint.py.

=== Settings (set in docker-compose.yml → environment) ===

  SEAF_INGEST_DAYS   Integer. Only include files modified within this many days.
                     Leave unset or blank to include all files regardless of age.
                     Examples:  365 (1 year)  730 (2 years)  1825 (5 years)

  SEAF_SETTINGS_URL  Optional. URL to a JSON settings endpoint (e.g. the
                     nas-settings panel's /api/settings route). When set, the
                     app fetches per-library ingest_days keyed by SEAF_LIBRARY
                     UUID at startup and on every hourly refresh. On fetch
                     failure it falls back silently to SEAF_INGEST_DAYS.
"""
import json
import logging
import os
import shutil
import threading
import time
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
log = logging.getLogger('seaf-entrypoint')

SOURCE = Path('/source')
LIBRARY = Path('/library')
UPSTREAM = '/home/seafile/entrypoint.py'


def fetch_ingest_days_from_url(settings_url: str, library_uuid: str, fallback) -> object:
    """
    Fetch per-library ingest_days from the settings API.

    Returns the integer ingest_days value for the matching library, or
    `fallback` if the fetch fails or the library is not found.
    """
    try:
        with urllib.request.urlopen(settings_url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for entry in data.values():
            if entry.get("uuid") == library_uuid:
                days = entry.get("ingest_days")
                # None means "all files" — pass through as-is
                log.info(
                    'Settings URL: ingest_days=%s for library %s',
                    days if days is not None else 'all',
                    library_uuid,
                )
                return days
        log.warning('Settings URL: library %s not found in response, using fallback', library_uuid)
    except Exception as exc:
        log.warning('Settings URL fetch failed (%s), using fallback SEAF_INGEST_DAYS', exc)
    return fallback


def resolve_ingest_days(env_days, settings_url: str | None, library_uuid: str | None):
    """
    Return the effective ingest_days value.

    Priority: SEAF_SETTINGS_URL (if reachable and library found) > SEAF_INGEST_DAYS env var.
    """
    if settings_url and library_uuid:
        return fetch_ingest_days_from_url(settings_url, library_uuid, fallback=env_days)
    return env_days


def populate(days=None):
    """Populate /library from /source, filtered to files modified within `days` days."""
    cutoff = time.time() - days * 86400 if days else 0

    wanted = set()
    for root, _dirs, files in os.walk(SOURCE):
        rp = Path(root)
        for fname in files:
            fp = rp / fname
            try:
                if not days or fp.stat().st_mtime >= cutoff:
                    wanted.add(fp.relative_to(SOURCE))
            except OSError:
                pass

    log.info('Ingest window: %s days — %d qualifying files', days or 'all', len(wanted))

    # Remove entries from library that are no longer wanted
    for root, _dirs, files in os.walk(LIBRARY, topdown=False):
        rp = Path(root)
        for fname in files:
            lp = rp / fname
            if lp.relative_to(LIBRARY) not in wanted:
                lp.unlink(missing_ok=True)
        if rp != LIBRARY:
            try:
                rp.rmdir()
            except OSError:
                pass

    # Copy new or updated files into library
    copied = 0
    for rel in wanted:
        src = SOURCE / rel
        dst = LIBRARY / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            src_mtime = src.stat().st_mtime
            if not dst.exists() or src_mtime > dst.stat().st_mtime:
                shutil.copy2(src, dst)
                copied += 1
        except OSError as e:
            log.warning('Skip %s: %s', rel, e)

    log.info('Library ready — %d files updated', copied)


def refresh_loop(env_days, settings_url, library_uuid):
    def _run():
        while True:
            time.sleep(3600)
            log.info('Hourly refresh — re-populating library')
            days = resolve_ingest_days(env_days, settings_url, library_uuid)
            populate(days)
    threading.Thread(target=_run, daemon=True).start()


if __name__ == '__main__':
    raw = os.environ.get('SEAF_INGEST_DAYS', '').strip()
    env_days = int(raw) if raw else None
    log.info('SEAF_INGEST_DAYS=%s', env_days if env_days else 'not set (all files)')

    settings_url = os.environ.get('SEAF_SETTINGS_URL', '').strip() or None
    library_uuid = os.environ.get('SEAF_LIBRARY', '').strip() or None
    if settings_url:
        log.info('SEAF_SETTINGS_URL=%s', settings_url)

    days = resolve_ingest_days(env_days, settings_url, library_uuid)
    populate(days)
    refresh_loop(env_days, settings_url, library_uuid)
    os.execv(UPSTREAM, [UPSTREAM])
