---
summary: Detail moved out of AGENTS.md: repository structure, modification inventory, task-to-file navigation, and the credentials/environment variable table.
kind: living
status: current
read-when: AGENTS.md points here for the file map, modification inventory, task-to-file map or env table
---

Reference detail moved out of AGENTS.md on 2026-11-11 so the router stays small. Section numbering follows the old AGENTS.md order.


Project-owned code:

- `seafile-server/nas-settings/` - Flask admin panel and tests for status, controls, config, libraries, ingest windows, sync schedules, and cached folder-size display.
- `synology-seaf-cli/` - Docker wrapper image for `seaf-cli`, including staging, daemon supervision, status reporter, command dispatcher, schedule enforcement, and folder-size cache scanner.
- `seafile-server/custom-templates/` - Seahub template overrides for the Microsoft login button and admin-only NAS Sync links.

Docs:

- `README.md` - quick entry point and orientation.
- `AGENTS.md` - canonical AI/developer operating guide and documentation router.
- `CLAUDE.md` - Claude Code-specific instructions only.
- `docs/architecture.md` - system design, components, data flow, constraints.
- `docs/development.md` - local setup, run/test/lint/debug workflow.
- `docs/configuration.md` - environment variables, config files, feature flags.
- `docs/deployment.md` - deploy/release/environment/rollback workflow.
- Folder READMEs: `seafile-server/nas-settings/README.md`, `synology-seaf-cli/README.md`, `seafile-server/custom-templates/README.md`.
- `HANDOFF.md` - temporary continuation doc only when work is unfinished, blocked, or partially deployed.

Scripts:

- `seafile-server/START_SEAFILE.sh` - VPS pre-flight/start helper.
- `seafile-server/CONFIGURE_OAUTH.sh` - old one-time Google OAuth script; already applied historically and now obsolete for Microsoft SSO. Do not run.
- `seafile-server/CREATE_NAS_SYNC_ACCOUNT.sh` - one-time machine-account script; do not rerun.

Deployment files:

- `seafile-server/seafile-server.yml`, `seafile-server/caddy.yml`, `seafile-server/nas-settings.yml`.
- `synology-seaf-cli/docker-compose.yml`.
- `.github/workflows/seaf-cli-image.yml`, `.github/workflows/nas-settings-image.yml`.

Migrations:

- No project-owned database migrations exist. Seafile owns its MariaDB schemas (`ccnet_db`, `seafile_db`, `seahub_db`).

Generated / third-party / vendor / framework code:

- No vendored source tree is committed. Upstream code lives in images: `seafileltd/seafile-pro-mc:13.0-latest`, `flrnnc/seafile-client:latest`, `mariadb:10.11`, `redis`, and `lucaslorentz/caddy-docker-proxy:2.12-alpine`.

Build artifacts:

- None should be committed. CI publishes images to GHCR; local Python caches and secret dumps are ignored.



| File | Change made | Why it was necessary | Risk during upgrades |
|---|---|---|---|
| `seafile-server/custom-templates/sysadmin/sysadmin_react_app.html` | Full Seahub template copy with injected admin sidebar link to `/nas-settings/` | Seafile has no plugin hook for adding a custom System Admin page link | Re-diff against the upstream template after Seafile upgrades; a stale copy can break the sysadmin UI |
| `seafile-server/custom-templates/react_app.html` | Full Seahub main app template copy with admin-only NAS Sync sidebar link | Lets admins reach the panel from the main Seafile UI; non-admins do not see a dead admin link | Re-diff after Seafile upgrades; a template syntax error can break the main app page |
| `seafile-server/custom-templates/registration/login.html` | Seahub login template copy with the official Microsoft sign-in button/logo wired to Seafile's SSO click handler | Replaces generic "Single Sign-On" UI with the correct Microsoft SSO affordance | Re-diff after Seafile login template changes; broken markup can affect login |
| `seafile-server/custom-templates/sysadmin/sudo_mode.html` | Seahub admin sudo-mode template copy with the official Microsoft sign-in button wired to Seafile's SSO route | Lets SSO-only admins confirm admin access without a local password; local password remains available as fallback | Re-diff after Seafile upgrades; broken markup can affect admin entry |

No upstream source files are modified in-repo; these are runtime template overrides layered through Seafile's custom-template directory.



| Task | Files to touch | Files not to touch |
|---|---|---|
| Change login screen | `seafile-server/custom-templates/registration/login.html`, `seafile-server/custom-templates/README.md` | Installed Seahub files inside the `seafile` container |
| Change admin/main NAS Sync links or admin confirmation UI | `seafile-server/custom-templates/sysadmin/sysadmin_react_app.html`, `seafile-server/custom-templates/sysadmin/sudo_mode.html`, `seafile-server/custom-templates/react_app.html` | Unrelated Seahub templates |
| Change NAS Settings panel behavior | `seafile-server/nas-settings/app.py`, `seafile-server/nas-settings/templates/`, `seafile-server/nas-settings/test_app.py`, `seafile-server/nas-settings/README.md` | `seafile-server/seafile-server.yml` unless runtime wiring changes |
| Add/change sync schedule UI | `seafile-server/nas-settings/app.py`, `seafile-server/nas-settings/templates/settings.html`, `synology-seaf-cli/entrypoint.py`, tests | Manual per-container edits on the NAS |
| Add/change cached folder-size view | `synology-seaf-cli/entrypoint.py`, `seafile-server/nas-settings/templates/libraries.html`, tests, relevant READMEs | Live recursive folder-size calculation in Seahub file browsing |
| Change seaf-cli sync behavior | `synology-seaf-cli/entrypoint.py`, `synology-seaf-cli/test_entrypoint.py`, `synology-seaf-cli/README.md` | Upstream `flrnnc/seafile-client` image code or manual live container edits |
| Add a synced NAS library | `synology-seaf-cli/docker-compose.yml`, `seafile-server/nas-settings/app.py` `LIBRARIES`, docs identifiers | Reusing an existing library UUID or data volume |
| Change VPS containers | `seafile-server/seafile-server.yml`, `seafile-server/caddy.yml`, `seafile-server/nas-settings.yml`, `docs/deployment.md`, `docs/configuration.md` | Container names unless a migration plan exists |
| Change CI build/publish | `.github/workflows/seaf-cli-image.yml`, `.github/workflows/nas-settings-image.yml`, `docs/deployment.md` | Add SSH deploy steps to CI |
| Change runtime env vars | Example env files, compose files, `docs/configuration.md`, `AGENTS.md` credential table | Committed real `.env` files |
| Change Microsoft OAuth settings | Live `/opt/seafile-data/seafile/conf/seahub_settings.py` with backup, then `docs/configuration.md` | `seafile-server/CONFIGURE_OAUTH.sh` |
| Share all libraries with users | Prefer Seafile GUI group shares or Seafile API; document policy if changed | Direct SQL unless API/GUI cannot perform the operation |
| Update canonical operating guidance | `AGENTS.md` first; supporting docs only for topic-specific detail | Duplicating the same details in every README |



Never commit actual secret values.

| Variable | Purpose | Stored where | Required in dev | Required in prod |
|---|---|---|---|---|
| `COMPOSE_FILE` | Default VPS compose files | `/opt/seafile/.env`, `seafile-server/.env.example` | no | yes |
| `COMPOSE_PATH_SEPARATOR` | Compose file separator | `/opt/seafile/.env`, `seafile-server/.env.example` | no | yes |
| `SEAFILE_IMAGE` | Seafile Pro image | `/opt/seafile/.env`, `seafile-server/.env.example` | no | yes |
| `SEAFILE_DB_IMAGE` | MariaDB image | `/opt/seafile/.env`, `seafile-server/.env.example` | no | yes |
| `SEAFILE_REDIS_IMAGE` | Redis image | `/opt/seafile/.env`, `seafile-server/.env.example` | no | yes |
| `SEAFILE_CADDY_IMAGE` | Caddy image | `/opt/seafile/.env`, `seafile-server/.env.example` | no | yes |
| `SEAFILE_VOLUME` | Seafile data mount | `/opt/seafile/.env`, `seafile-server/.env.example` | no | yes |
| `SEAFILE_MYSQL_VOLUME` | MariaDB data mount | `/opt/seafile/.env`, `seafile-server/.env.example` | no | yes |
| `SEAFILE_CADDY_VOLUME` | Caddy TLS/state mount | `/opt/seafile/.env`, `seafile-server/.env.example` | no | yes |
| `SEAFILE_SERVER_HOSTNAME` | Public hostname | `/opt/seafile/.env`, `seafile-server/.env.example` | no | yes |
| `SEAFILE_SERVER_PROTOCOL` | Public protocol / Caddy label | `/opt/seafile/.env`, `seafile-server/.env.example` | no | yes |
| `TIME_ZONE` | Server timezone | `/opt/seafile/.env`, `seafile-server/.env.example`, `seahub_settings.py` | no | yes |
| `JWT_PRIVATE_KEY` | Internal Seafile token signing | `/opt/seafile/.env` | no | yes |
| `SEAFILE_MYSQL_DB_HOST` | DB host/service | `/opt/seafile/.env`, compose | no | yes |
| `SEAFILE_MYSQL_DB_PORT` | DB port | compose default | no | yes |
| `SEAFILE_MYSQL_DB_USER` | DB username | `/opt/seafile/.env`, compose | no | yes |
| `SEAFILE_MYSQL_DB_PASSWORD` | DB password | `/opt/seafile/.env` | no | yes |
| `SEAFILE_MYSQL_DB_CCNET_DB_NAME` | ccnet DB name | `/opt/seafile/.env`, compose | no | yes |
| `SEAFILE_MYSQL_DB_SEAFILE_DB_NAME` | seafile DB name | `/opt/seafile/.env`, compose | no | yes |
| `SEAFILE_MYSQL_DB_SEAHUB_DB_NAME` | seahub DB name | `/opt/seafile/.env`, compose | no | yes |
| `INIT_SEAFILE_ADMIN_EMAIL` | First-start admin email | `/opt/seafile/.env`, example | no | init only |
| `INIT_SEAFILE_ADMIN_PASSWORD` | First-start admin password | `/opt/seafile/.env` | no | init only |
| `INIT_SEAFILE_MYSQL_ROOT_PASSWORD` | MariaDB root password | `/opt/seafile/.env` | no | yes |
| `CACHE_PROVIDER` | Seafile cache backend | `/opt/seafile/.env`, compose | no | yes |
| `REDIS_HOST` | Redis host | `/opt/seafile/.env`, compose | no | yes |
| `REDIS_PORT` | Redis port | `/opt/seafile/.env`, compose | no | yes |
| `REDIS_PASSWORD` | Redis password, empty in current internal network setup | `/opt/seafile/.env` | no | optional |
| `SEAF_SERVER_STORAGE_TYPE` | Storage backend selector | `/opt/seafile/.env`, example | no | yes |
| `S3_BLOCK_BUCKET` | S3 blocks bucket | `/opt/seafile/.env`, example | no | yes |
| `S3_COMMIT_BUCKET` | S3 commits bucket | `/opt/seafile/.env`, example | no | yes |
| `S3_FS_BUCKET` | S3 fs bucket | `/opt/seafile/.env`, example | no | yes |
| `S3_KEY_ID` | S3 access key ID | `/opt/seafile/.env` | no | yes |
| `S3_SECRET_KEY` | S3 secret key | `/opt/seafile/.env` | no | yes |
| `S3_USE_V4_SIGNATURE` | S3 signing option | `/opt/seafile/.env`, example | no | yes |
| `S3_AWS_REGION` | S3 region | `/opt/seafile/.env`, example | no | yes |
| `S3_HOST` | S3-compatible endpoint | `/opt/seafile/.env`, example | no | yes |
| `S3_USE_HTTPS` | S3 HTTPS toggle | `/opt/seafile/.env`, example | no | yes |
| `S3_PATH_STYLE_REQUEST` | S3 URL style | `/opt/seafile/.env`, example | no | yes |
| `S3_SSE_C_KEY` | Optional S3 client-side encryption key | `/opt/seafile/.env`, example | no | optional |
| `ENABLE_SEADOC` | Seadoc feature toggle | `/opt/seafile/.env`, compose | no | yes |
| `ENABLE_NOTIFICATION_SERVER` | Notification feature toggle | `/opt/seafile/.env`, compose | no | yes |
| `ENABLE_SEAFILE_AI` | AI feature toggle | `/opt/seafile/.env`, compose | no | yes |
| `ENABLE_FACE_RECOGNITION` | Face recognition toggle | `/opt/seafile/.env`, compose | no | yes |
| `NAS_SETTINGS_SECRET_KEY` | Flask session signing, passed as `SECRET_KEY` | `/opt/seafile/.env` | test value only | yes |
| `NAS_STATUS_TOKEN` | Shared NAS status token, passed as `STATUS_TOKEN`/`SEAF_STATUS_TOKEN` | `/opt/seafile/.env` and NAS env | test value only | yes |
| `SECRET_KEY` | Runtime env inside `nas-settings` | `seafile-server/nas-settings.yml` from `NAS_SETTINGS_SECRET_KEY` | yes for tests | yes |
| `STATUS_TOKEN` | Runtime env inside `nas-settings` | `seafile-server/nas-settings.yml` from `NAS_STATUS_TOKEN` | yes for tests | yes |
| `SEAFILE_INTERNAL_URL` | Internal Seafile URL for admin checks | `seafile-server/nas-settings.yml` | no | yes |
| `SEAFILE_PUBLIC_HOST` | Public host used by panel | `seafile-server/nas-settings.yml` | no | yes |
| `SEAF_SERVER_URL` | Seafile URL for seaf-cli | NAS compose/env | no | yes |
| `SEAF_USERNAME` | seaf-cli account username | NAS `/tmp/.env` | no | yes |
| `SEAF_PASSWORD` | seaf-cli account password | NAS `/tmp/.env` | no | yes |
| `SEAF_TOKEN` | Optional seaf-cli auth token alternative | environment only if used | no | optional |
| `SEAF_LIBRARY_<KEY>` | Multi-library UUID mapping; key maps to `/library/<key>` | NAS compose | no | yes |
| `SEAF_LIBRARY` | Legacy single-library UUID; if set, multi-library vars are ignored | single-library env only | no | optional |
| `SEAF_LIBRARY_UUID` | Legacy seaf-cli library UUID env | code supports legacy | no | no |
| `SEAF_LIBRARY_PASSWORD` | Optional encrypted-library password | environment only if used | no | optional |
| `SEAF_SETTINGS_URL` | Panel settings endpoint for NAS agent | NAS compose | no | yes |
| `SEAF_STATUS_TOKEN` | NAS agent status token | NAS env | no | yes |
| `SEAF_CONTAINER_NAME` | Container identifier for the panel memory-limit update API | environment only if used; defaults to hostname | no | optional |
| `SEAF_UPLOAD_LIMIT` | Optional seaf-cli upload speed cap | environment only if used | no | optional |
| `SEAF_DOWNLOAD_LIMIT` | Optional seaf-cli download speed cap | environment only if used | no | optional |
| `SEAF_SKIP_SSL_CERT` | Optional TLS verification skip | environment only if used | no | optional |
| `SEAF_2FA_SECRET` | Optional TOTP secret for seaf-cli auth | environment only if used | no | optional |
| `DEBUG` | NAS agent debug logging | environment only if used | no | optional |
| `GITHUB_TOKEN` | GitHub Actions package publish token | GitHub Actions built-in secret | no | CI only |
| `CF_TOKEN` | Cloudflare DNS API token | operator-provided, not committed | no | only for DNS changes |

Other secret material lives in `/opt/seafile/CREDENTIALS.txt` on the VPS, root-only. Do not paste or commit it.
