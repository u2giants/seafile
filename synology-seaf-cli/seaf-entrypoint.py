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
"""
import logging
import os
import shutil
import threading
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
log = logging.getLogger('seaf-entrypoint')

SOURCE = Path('/source')
LIBRARY = Path('/library')
UPSTREAM = '/home/seafile/entrypoint.py'


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


def refresh_loop(days=None):
    def _run():
        while True:
            time.sleep(3600)
            log.info('Hourly refresh — re-populating library')
            populate(days)
    threading.Thread(target=_run, daemon=True).start()


if __name__ == '__main__':
    raw = os.environ.get('SEAF_INGEST_DAYS', '').strip()
    days = int(raw) if raw else None
    log.info('SEAF_INGEST_DAYS=%s', days if days else 'not set (all files)')
    populate(days)
    refresh_loop(days)
    os.execv(UPSTREAM, [UPSTREAM])
