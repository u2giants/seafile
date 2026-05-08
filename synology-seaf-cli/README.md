# Synology NAS — seaf-cli Sync

Syncs folders from the NYC Synology NAS to Seafile Pro on the Linode VPS.

## Setup

1. Install Docker on the Synology (via Package Center → Container Manager)
2. Copy `.env.example` to `.env` and fill in `NAS_SYNC_PASSWORD` (from CREDENTIALS.txt on the VPS)
3. Adjust the volume paths under each service to match the actual NAS folder locations (e.g. `/volume1/ActiveProjects` may differ)
4. Deploy: `docker compose up -d`

## Libraries

| Container | NAS Folder | Seafile Library | UUID |
|-----------|-----------|-----------------|------|
| seaf-cli-active-projects | /volume1/ActiveProjects | Active Projects | 0dee1650-878e-4ca3-9533-e3876ebd4c1e |
| seaf-cli-assets | /volume1/Assets | Assets | 09afbd46-87c6-45b5-a305-431310af20a5 |
| seaf-cli-seasonal | /volume1/Seasonal | Seasonal | 8108c1df-6dc1-4e22-bc1f-4eb8e8ef5d2b |

## Credentials (stored on VPS)

- Server: `https://seafile.designflow.app`
- Username: `nas-sync@popcre.com`
- Password: see `/opt/seafile/CREDENTIALS.txt` on the VPS (172.233.14.233)

## Notes

- Initial sync of large libraries (28TB) will take significant time — leave containers running
- Containers restart automatically on NAS reboot (`restart: unless-stopped`)
- Add more services to docker-compose.yml if additional NAS folders need syncing
