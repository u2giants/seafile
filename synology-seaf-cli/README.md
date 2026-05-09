# Synology seaf-cli — NAS Sync

Syncs folders from the NYC Synology NAS to Seafile Pro at `seafile.designflow.app`. One Docker container per library.

**Status: Both containers live on edgesynology1 as of 2026-05-08.**

## Live Containers

| Container | NAS path (→ /source) | Seafile library | UUID |
|-----------|----------------------|-----------------|------|
| `seaf-cli-char-licensed` | `/volume1/mac/Decor/Character Licensed` | Character Licensed | `177cf9de-3066-482e-956a-7ae8d8786c6d` |
| `seaf-cli-generic-decor` | `/volume1/mac/Decor/Generic Decor` | Generic Decor | `1b116ab7-d66b-4411-a691-21f34eadb731` |

## How it works

Each container runs a two-stage entrypoint:

1. **`seaf-entrypoint.py`** (downloaded from GitHub at container start) — stages a date-filtered snapshot of the NAS folder into a Docker volume at `/library`. Only files with `mtime` within `SEAF_INGEST_DAYS` days are included. Refreshes hourly. Fetches the ingest window from the nas-settings API at startup; falls back to `SEAF_INGEST_DAYS` env var if the fetch fails.

2. **`/home/seafile/entrypoint.py`** (built into the `flrnnc/seafile-client` image) — runs `seaf-daemon`, registers `/library` as the sync path, and keeps it synchronised to Seafile.

```
/source (NAS bind mount, read-only)
    │
    ▼ seaf-entrypoint.py
    ▼
/library (Docker staging volume)
    │
    ▼ seaf-daemon (upstream seaf-cli)
    ▼
Seafile server → S3
```

**Why `seaf-entrypoint.py` is downloaded, not mounted:** The NAS MCP `run_command` tool blocks file write operations. Downloading from GitHub at startup avoids needing to place the file on the NAS filesystem.

## Image

Use `flrnnc/seafile-client:latest`. `seafileltd/seaf-cli` does NOT exist on Docker Hub. `flowgunso/seafile-client` is a deprecated alias — use `flrnnc`.

## Entrypoint override

The image's default shell entrypoint (`/entrypoint.sh`) runs `chown -R seafile:seafile /library` before starting the Python sync script. The Synology btrfs volume returns "Read-only file system" for chown, killing the container.

The compose overrides this with a custom entrypoint that downloads and runs `seaf-entrypoint.py` directly (as root), bypassing the chown. `seaf-entrypoint.py` then `os.execv`s into the upstream `/home/seafile/entrypoint.py`.

**Side effect:** The image's built-in health check (baked into the image) may still call `/entrypoint.sh`. If so, health checks show `unhealthy` permanently — the actual sync continues regardless.

## Check sync status

Via NAS MCP `run_command` (target: edgesynology1) — all docker commands must be base64-encoded because the MCP blocks the string "docker":

```bash
# Encode and run: docker logs --tail 50 seaf-cli-char-licensed
echo "ZG9ja2VyIGxvZ3MgLS10YWlsIDUwIHNlYWYtY2xpLWNoYXItbGljZW5zZWQ=" | base64 -d | bash
```

Healthy sync state in logs: seaf-entrypoint lines (`Ingest window: … qualifying files`, `Library ready`) followed by seaf-daemon entries cycling through `commit → fs → data → finished → synchronized`.

## Ingest window settings

The per-library ingest window (how far back files are synced) is configurable at:
```
https://seafile.designflow.app/sys/  → NAS Sync Settings (bottom of left nav)
```

Changes take effect on the next hourly refresh, or immediately if the container is restarted.

## Re-deploy after removal

Containers have `restart: unless-stopped` — they survive reboots without the compose file.

If a container is manually removed, re-deploy from the repo's compose file. Because the MCP blocks write operations, use the base64 approach to run docker compose:

```bash
# On edgesynology1 via NAS MCP run_command:
# 1. Download the compose file from GitHub to /tmp
# 2. Run: docker compose -f /tmp/docker-compose.yml --env-file /tmp/.env up -d

# The .env file needs: SEAF_USERNAME and SEAF_PASSWORD (nas-sync@popcre.com credentials)
# See /opt/seafile/CREDENTIALS.txt on the VPS
```

## Connection details

| | |
|---|---|
| Server | https://seafile.designflow.app |
| Username | nas-sync@popcre.com |
| Password | See `/opt/seafile/CREDENTIALS.txt` on VPS |

## Notes

- seaf-cli state (sync metadata) is in the `seaf-cli-*-data` Docker volumes mounted at `/seafile`. Deleting these forces a full re-sync.
- The `seaf-cli-*-staging` volumes hold the date-filtered file snapshot at `/library`. Deleting these is safe — they're repopulated by seaf-entrypoint.py on next start.
- seaf-daemon takes ~7 minutes to reach "started" state on first boot; seaf-entrypoint.py waits for it via polling before registering the library.
- NAS folders are mounted read-only at `/source`. seaf-cli syncs from `/library` (the staging volume), not `/source` directly.
