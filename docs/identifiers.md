---
summary: External identifiers: library UUIDs and NAS paths, accounts, Entra tenant and app, DNS records, S3 buckets, images; plus the container inventory.
kind: living
status: current
read-when: looking up a UUID, account, bucket, DNS record or container name
---

Data model, external identifiers, and the container/service inventory, moved out of AGENTS.md on 2026-11-11. Do not casually rename, regenerate, or replace documented identifiers.


| Entity/System | Identifier | Where defined | Notes |
|---|---|---|---|
| GitHub repo | `https://github.com/u2giants/seafile` | Git remote | Pull requests to `main`; never push directly |
| Public host | `seafile.designflow.app` | `seafile-server/.env.example`, compose labels, live DNS | DNS-only through Cloudflare; do not proxy |
| VPS | `172.233.14.233`, host `seafile-br` | docs/live host | Linode VPS running Seafile and `nas-settings`; do not confuse with other Hetzner/Tailscale hosts that may have stale repo clones |
| NAS | `edgesynology1` (private address in the protected recovery reference) | docs/runtime | Synology NAS; from the VPS use `ssh edge1` as `ai` over Tailscale MagicDNS |
| Microsoft Entra tenant | `1caeb1c0-a087-4cb9-b046-a5e22404f971` | live `seahub_settings.py`, docs | Tenant-locked POP Creations SSO |
| Entra app/client | `8d9da03c-e5cd-4a23-b987-32aaaed31fe7` | live `seahub_settings.py`, docs | Client secret value is not committed |
| Seafile admin account | `4cba3f5721f7436fbe06a2b154ee296a@auth.local` | `ccnet_db.EmailUser`, `seahub_db.profile_profile` | Contact email `albert@popcre.com`; current active admin |
| NAS sync account | `95520c9b8c914cddb93d8d1bf65fa528@auth.local` | `ccnet_db.EmailUser`, `seahub_db.profile_profile` | Contact email `nas-sync@popcre.com`; non-admin machine account |
| Character Licensed library | `177cf9de-3066-482e-956a-7ae8d8786c6d` | `synology-seaf-cli/docker-compose.yml`, `seafile-server/nas-settings/app.py`, database | NAS path `/volume1/mac/Decor/Character Licensed`; owner is current SSO admin |
| Generic Decor library | `1b116ab7-d66b-4411-a691-21f34eadb731` | `synology-seaf-cli/docker-compose.yml`, `seafile-server/nas-settings/app.py`, database | NAS path `/volume1/mac/Decor/Generic Decor`; owner is current SSO admin |
| Styleguides library | `b6e1d4c9-434e-4d8a-bde2-7f19be9c0838` | `synology-seaf-cli/docker-compose.yml` | NAS path `/volume1/styleguides`; synced by the current single NAS `seaf-cli` container |
| ArtLibrary library | `d28d5118-e991-431a-be3d-2e6a15246479` | `synology-seaf-cli/docker-compose.yml`, `seafile-server/nas-settings/app.py`, database | NAS path `/volume1/mac/Art Library`; synced by the current single NAS `seaf-cli` container |
| shared library | `0eac5726-a5b4-4fc4-a1a3-00e87048f5b6` | `synology-seaf-cli/docker-compose.yml`, `seafile-server/nas-settings/app.py`, database | NAS path `/volume1/files/shared`; owner is current SSO admin; synced by the single NAS `seaf-cli` container |
| Current internal public shares | `InnerPubRepo.permission = r` for both NAS libraries | `seafile_db.InnerPubRepo` | Means all logged-in users can read. For read-write, use group/user shares with write permission |
| S3 block bucket | `seafile-s3` | `.env`, `docs/configuration.md` | Linode Object Storage `br-gru-1` |
| S3 commit bucket | `seafile-s3-commits` | `.env`, `docs/configuration.md` | Must remain distinct |
| S3 fs bucket | `seafile-s3-fs` | `.env`, `docs/configuration.md` | Must remain distinct |
| Cloudflare zone | `921eb133a3f7d5802780445b283f84ce` | docs/runtime | Token value is not committed |
| Cloudflare DNS record | `2c1cdc08f9f79d9d668970854d9e15a8` | docs/runtime | DNS-only A record for Seafile host |
| seaf-cli image | `ghcr.io/u2giants/seafile:seaf-cli-latest`, `ghcr.io/u2giants/seafile:sha-<commit>` | `.github/workflows/seaf-cli-image.yml` | CI-built; deploy by pull/recreate |
| nas-settings image | `ghcr.io/u2giants/seafile:nas-settings-latest`, `ghcr.io/u2giants/seafile:nas-settings-sha-<commit>` | `.github/workflows/nas-settings-image.yml` | CI-built; deploy by pull/recreate |

Do not casually rename, regenerate, or replace documented identifiers.



| Container/service | Purpose | Managed by | App/project ID | Image/source |
|---|---|---|---|---|
| `seafile` | Seafile Pro app, Seahub, fileserver | Docker Compose on VPS | none/Coolify not used | `seafileltd/seafile-pro-mc:13.0-latest` |
| `seafile-mysql` | MariaDB metadata database | Docker Compose on VPS | none | `mariadb:10.11` |
| `seafile-redis` | Redis cache/session support | Docker Compose on VPS | none | `redis` |
| `seafile-caddy` | Caddy reverse proxy and TLS | Docker Compose on VPS | none | `lucaslorentz/caddy-docker-proxy:2.12-alpine` |
| `nas-settings` | Flask admin panel and NAS command/status API | Docker Compose on VPS, image from GitHub Actions | none | `ghcr.io/u2giants/seafile:nas-settings-latest` |
| `seaf-cli` | Syncs Character Licensed, Generic Decor, Styleguides, ArtLibrary, and shared NAS folders to Seafile | Docker Compose on `edgesynology1` NAS | none | `ghcr.io/u2giants/seafile:seaf-cli-latest` |

There is no Coolify, Supabase, deploy app ID, or webhook deploy target for this project.
