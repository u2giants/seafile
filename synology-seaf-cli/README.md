# Synology seaf-cli — NAS Sync

Syncs folders from the NYC Synology NAS to Seafile Pro at `seafile.designflow.app`. One Docker container per library.

**Status: Not yet deployed.**

## Prerequisites

- Synology Container Manager installed (Package Center)
- SSH access to the Synology, or Container Manager UI available
- NAS sync password from `/opt/seafile/CREDENTIALS.txt` on the VPS

## Setup

1. Copy `.env.example` to `.env` and set `NAS_SYNC_PASSWORD` (from CREDENTIALS.txt on VPS at 172.233.14.233)

2. Adjust the volume source paths under each service to match the actual Synology volume layout:
   ```yaml
   volumes:
     - /volume1/ActiveProjects:/data/sync   # ← change /volume1/ActiveProjects if needed
   ```

3. Deploy:
   ```bash
   docker compose up -d
   ```

4. Check sync status:
   ```bash
   docker logs seaf-cli-active-projects
   docker logs seaf-cli-assets
   docker logs seaf-cli-seasonal
   ```

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
