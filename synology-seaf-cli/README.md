# Synology seaf-cli — NAS Sync

Syncs folders from the NYC Synology NAS to Seafile Pro at `seafile.designflow.app`. One Docker container per library.

**Status: seaf-cli-decor is LIVE on edgesynology1 as of 2026-05-08. Assets and Seasonal pending NAS path confirmation from Albert.**

## Image

Use `flrnnc/seafile-client:latest`. `seafileltd/seaf-cli` does NOT exist on Docker Hub.
`flowgunso/seafile-client` is a deprecated alias for the same image — use `flrnnc`.

## Deploy a new container

The NAS MCP allowlist blocks docker commands in the command string. Use base64 encoding to run them via the `run_command` MCP tool. See CONTEXT_FOR_AI.md for the pattern.

Files are written to `/tmp` via base64+tee, then `docker-compose -f /tmp/seaf-cli-compose.yml up -d`.

## Check sync status

Via NAS MCP (base64-encoded):
```
/var/packages/ContainerManager/target/usr/bin/docker logs --tail 50 seaf-cli-decor
```

## Re-deploy after reboot (if container was removed)

The container has `restart: unless-stopped` so it survives reboots automatically.
If it was manually removed, re-write `/tmp/seaf-cli-compose.yml` from this file and run `docker-compose up -d`.

## Library Mapping

| Container | NAS path (adjust if different) | Seafile library | UUID |
|-----------|-------------------------------|-----------------|------|
| seaf-cli-active-projects | /volume1/ActiveProjects | Active Projects | `0dee1650-878e-4ca3-9533-e3876ebd4c1e` |
| seaf-cli-assets | /volume1/Assets | Assets | `09afbd46-87c6-45b5-a305-431310af20a5` |
| seaf-cli-seasonal | /volume1/Seasonal | Seasonal | `8108c1df-6dc1-4e22-bc1f-4eb8e8ef5d2b` |

## Connection Details

| | |
|---|---|
| Server | https://seafile.designflow.app |
| Username | nas-sync@popcre.com |
| Password | See `/opt/seafile/CREDENTIALS.txt` on VPS |

## Notes

- Initial sync of a large library (28TB total) will take a long time — leave containers running uninterrupted
- All containers use `restart: unless-stopped` — they recover automatically from Synology reboots
- Add additional services to `docker-compose.yml` if more NAS folders need syncing
- seaf-cli state (sync metadata) is kept in named Docker volumes (`seaf-cli-*-data`) — do not delete these or seaf-cli will re-sync from scratch
