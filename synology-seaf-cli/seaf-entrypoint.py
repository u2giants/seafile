#!/usr/bin/env python3
from __future__ import annotations
"""
seaf-entrypoint.py

Staging wrapper for flrnnc/seafile-client. Hardlinks (or copies, if the source
and staging volume are on different filesystems) the subset of /source modified
within SEAF_INGEST_DAYS days into /library, then hands off to the upstream
entrypoint at /home/seafile/entrypoint.py.

=== Settings (set in docker-compose.yml → environment) ===

  SEAF_INGEST_DAYS   Integer. Only include files modified within this many days.
                     Leave unset or blank to include all files regardless of age.
                     Examples:  365 (1 year)  730 (2 years)  1825 (5 years)

  SEAF_SETTINGS_URL  Optional. URL to a JSON settings endpoint (e.g. the
                     nas-settings panel's /api/settings route). When set, the
                     app fetches per-library ingest_days keyed by SEAF_LIBRARY
                     UUID at startup and on every hourly refresh. On fetch
                     failure it falls back silently to SEAF_INGEST_DAYS.

  SEAF_IGNORE_DIRS   Optional comma-separated directory names to omit from the
                     staged library. Defaults to @eaDir so Synology metadata
                     folders are not uploaded to Seafile.
"""
import datetime
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
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
DEFAULT_IGNORE_DIRS = {"@eaDir"}


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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


def _same_filesystem(a, b):
    """True if paths a and b live on the same filesystem (hardlinks possible)."""
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def _place(src, dst, use_links):
    """Materialise src at dst — hardlink when possible, else copy.

    A hardlink shares the source's inode, so it costs ~0 extra disk and is
    near-instant regardless of file size. Falls back to a real copy on any
    error (cross-device link, link-count limits, a FS without hardlinks).
    """
    if use_links:
        try:
            os.link(src, dst)
            return
        except OSError:
            pass
    shutil.copy2(src, dst)


def _ignored_dir_names():
    raw = os.environ.get("SEAF_IGNORE_DIRS")
    if raw is None:
        return DEFAULT_IGNORE_DIRS
    return {name.strip() for name in raw.split(",") if name.strip()}


def cleanup_staging(reason: str = "exit") -> dict:
    """Remove all staged files from /library.

    This is intended only for the Windows/CIFS deployment where /library is a
    disposable Docker volume populated from /source. The caller must guard it
    with SEAF_CLEAN_STAGING_ON_EXIT so the NAS bind-mount deployment is never
    cleaned by accident.
    """
    if not LIBRARY.exists():
        return {"files": 0, "dirs": 0, "errors": 0}

    removed_files = 0
    removed_dirs = 0
    errors = 0
    for root, dirs, files in os.walk(LIBRARY, topdown=False):
        rp = Path(root)
        for fname in files:
            path = rp / fname
            try:
                path.unlink()
                removed_files += 1
            except OSError as exc:
                errors += 1
                log.warning("Cleanup skipped file %s: %s", path, exc)
        for dirname in dirs:
            path = rp / dirname
            try:
                path.rmdir()
                removed_dirs += 1
            except OSError as exc:
                errors += 1
                log.warning("Cleanup skipped directory %s: %s", path, exc)

    log.info(
        "Staging cleanup after %s — removed %d files and %d directories (%d errors)",
        reason,
        removed_files,
        removed_dirs,
        errors,
    )
    return {"files": removed_files, "dirs": removed_dirs, "errors": errors}


def scan_source(days, ignored_dirs=None):
    """Return {relpath: mtime} for source files modified within `days` days.

    Uses os.scandir so each file's mtime comes from the directory read itself
    rather than a second stat() syscall per file — roughly halving the metadata
    I/O of the hourly rescan over large trees (Character Licensed ≈ 467k files).
    """
    cutoff = time.time() - days * 86400 if days else 0
    ignored_dirs = DEFAULT_IGNORE_DIRS if ignored_dirs is None else set(ignored_dirs)
    wanted = {}
    stack = [SOURCE]
    while stack:
        current = stack.pop()
        try:
            scanner = os.scandir(current)
        except OSError:
            continue
        with scanner:
            for entry in scanner:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name in ignored_dirs:
                            continue
                        stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        mtime = entry.stat(follow_symlinks=False).st_mtime
                        if not days or mtime >= cutoff:
                            wanted[Path(entry.path).relative_to(SOURCE)] = mtime
                except OSError:
                    pass
    return wanted


def populate(days=None, ignored_dirs=None):
    """Mirror the in-window subset of /source into /library.

    /library is staged via hardlinks (falling back to copies) so the working
    set is never physically duplicated on the NAS. seaf-cli then syncs /library.
    """
    ignored_dirs = _ignored_dir_names() if ignored_dirs is None else set(ignored_dirs)
    wanted = scan_source(days, ignored_dirs)
    log.info(
        'Ingest window: %s days — %d qualifying files; ignored dirs: %s',
        days or 'all',
        len(wanted),
        ', '.join(sorted(ignored_dirs)) or 'none',
    )

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

    # Stage new or updated files. A hardlink shares the source inode, so its
    # mtime equals the source mtime — already-current files are skipped for free
    # on every refresh. A source file replaced in place carries a newer mtime
    # than its stale link, so it is re-linked.
    use_links = _same_filesystem(SOURCE, LIBRARY)
    placed = 0
    for rel, src_mtime in wanted.items():
        src = SOURCE / rel
        dst = LIBRARY / rel
        try:
            if dst.exists() and dst.stat().st_mtime >= src_mtime:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                dst.unlink()
            _place(src, dst, use_links)
            placed += 1
        except OSError as e:
            log.warning('Skip %s: %s', rel, e)

    method = 'hardlink' if use_links else 'copy'
    log.info('Library ready — %d files staged via %s', placed, method)
    try:
        Path('/tmp/ingest-status.json').write_text(json.dumps({
            "files": len(wanted),
            "changed_files": placed,
            "ingest_days": days,
            "method": method,
            "source_path": str(SOURCE),
            "source_label": os.environ.get("SEAF_SOURCE_PATH", str(SOURCE)),
            "staging_path": str(LIBRARY),
            "ignored_dirs": sorted(ignored_dirs),
            "last_ingest_at": datetime.datetime.utcnow().isoformat() + "Z",
        }))
    except OSError:
        pass


def refresh_loop(env_days, settings_url, library_uuid):
    # subprocess.run (not os.execv) keeps this process alive so the thread survives
    def _run():
        while True:
            time.sleep(3600)
            log.info('Hourly refresh — re-populating library')
            days = resolve_ingest_days(env_days, settings_url, library_uuid)
            populate(days)
    threading.Thread(target=_run, daemon=True).start()


def run_upstream() -> int:
    clean_on_exit = env_bool("SEAF_CLEAN_STAGING_ON_EXIT")
    cleanup_reason = "upstream exit"
    child = subprocess.Popen([sys.executable, UPSTREAM])

    def _stop(signum, _frame):
        nonlocal cleanup_reason
        cleanup_reason = f"signal {signum}"
        log.info("Received signal %s — forwarding to upstream entrypoint", signum)
        child.terminate()
        try:
            child.wait(timeout=45)
        except subprocess.TimeoutExpired:
            log.warning("Upstream entrypoint did not stop cleanly; killing it")
            child.kill()
            child.wait()
        sys.exit(128 + signum)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    try:
        return child.wait()
    finally:
        if clean_on_exit:
            cleanup_staging(cleanup_reason)


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
    # Keep this wrapper alive so the hourly refresh thread and signal cleanup
    # remain active while the upstream entrypoint supervises seaf-daemon.
    sys.exit(run_upstream())
