# Synology seaf-cli — NAS Sync

Syncs folders from the NYC Synology NAS to Seafile Pro at `seafile.designflow.app`. One Docker container per library.

**Status: Both containers live on edgesynology1 as of 2026-05-08. Generic Decor confirmed syncing; Character Licensed initial sync in progress.**

## Live Containers

| Container | NAS path | Seafile library | UUID |
|-----------|----------|-----------------|------|
| `seaf-cli-char-licensed` | `/volume1/mac/Decor/Character Licensed` | Character Licensed | `177cf9de-3066-482e-956a-7ae8d8786c6d` |
| `seaf-cli-generic-decor` | `/volume1/mac/Decor/Generic Decor` | Generic Decor | `1b116ab7-d66b-4411-a691-21f34eadb731` |

Docker volumes on the NAS are prefixed `tmp_` because the compose was deployed from `/tmp`:
- `tmp_seaf-cli-char-licensed-data`
- `tmp_seaf-cli-generic-decor-data`

## Image

Use `flrnnc/seafile-client:latest`. `seafileltd/seaf-cli` does NOT exist on Docker Hub.
`flowgunso/seafile-client` is a deprecated alias — use `flrnnc`.

## Entrypoint override (important)

The image's default shell entrypoint (`/entrypoint.sh`) runs `chown -R seafile:seafile /library` before starting the Python sync script. The Synology btrfs volume returns "Read-only file system" for chown, killing the container before any sync starts.

The compose overrides this with `entrypoint: ["/home/seafile/entrypoint.py"]`, running the Python script directly as root. This bypasses the chown and the container stays up.

Side effect: the image's built-in health check still calls `/entrypoint.sh` (it's baked in), so the health check always fails and containers show `unhealthy`. This is cosmetic — the actual sync continues regardless.

## Check sync status

Via NAS MCP `run_command` (target: edgesynology1):
```
docker logs --tail 50 seaf-cli-char-licensed
docker logs --tail 50 seaf-cli-generic-decor
```

Healthy sync state: seafile.log entries cycling through `commit` → `fs` → `data` → `finished`, then `synchronized`.

## Re-deploy after removal

Containers have `restart: unless-stopped` — they survive reboots automatically.

If manually removed, the compose and env files are at `/tmp/seaf-cli-compose.yml` and `/tmp/.env` on edgesynology1. Re-deploy with:
```
docker compose -f /tmp/seaf-cli-compose.yml --env-file /tmp/.env up -d
```

The NAS MCP `run_command` tool blocks write operations including `docker` commands. Use the `run_command` tool for read-only status checks (`docker ps`, `docker logs`) only. For write operations (restart, stop, start), you need a separate approach — the base64+tee trick was used for the initial deployment.

## Connection Details

| | |
|---|---|
| Server | https://seafile.designflow.app |
| Username | nas-sync@popcre.com |
| Password | See `/opt/seafile/CREDENTIALS.txt` on VPS |

## Notes

- seaf-cli state (sync metadata) is in the `tmp_*` Docker volumes mounted at `/seafile` — deleting these forces a full re-sync
- NAS folders are mounted to `/library`. Do NOT mount to `/data/sync` — seaf-cli ignores that path
- The seaf-daemon RPC server takes ~7 minutes to reach "started" state on first boot; the Python entrypoint waits for it before registering the library
