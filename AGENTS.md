# AGENTS.md - POP Creations Seafile Infrastructure

## Project summary

This repo operates POP Creations' Seafile Pro deployment at `seafile.designflow.app`: NYC Synology NAS design folders are uploaded by `seaf-cli` containers, stored in Linode Object Storage, and accessed by POP Creations staff through Seafile web/desktop clients. The important moving parts are the VPS Docker stack, the NAS sync containers, the `nas-settings` admin panel, Microsoft Entra SSO, and repo-driven CI images; the outcome that matters is reliable, auditable NAS-to-Seafile sync with safe admin controls.

## Multi-model AI note

There is no universal ignore-file standard across AI coding tools.

`.claudeignore` works for Claude Code.

When using any other AI tool, paste this file as your first message and follow the instructions in the "What to ignore" section.

## Documentation map: what to read for each task

Always start with:

- `AGENTS.md`

Then load additional docs only when relevant:

| Task / question | Read these docs | Usually do not need |
|---|---|---|
| Quick repo orientation | `README.md`, `AGENTS.md` | Deep docs under `docs/` unless task requires them |
| Modify app behavior or project-owned code | `AGENTS.md`, relevant folder-level `README.md`, `docs/architecture.md` if system design is affected | `docs/deployment.md` unless deploy behavior changes |
| Add or change configuration, env vars, feature flags, secrets, or runtime settings | `AGENTS.md`, `docs/configuration.md`, `docs/deployment.md` if prod/runtime env is affected | Unrelated architecture docs |
| Pull secrets from 1Password (MCP server or `op` CLI) | `AGENTS.md`, `docs/1password.md`, `docs/configuration.md` if env/config is affected | Deployment docs unless runtime env changes |
| Change local setup, dev scripts, test/lint/debug workflow, package scripts, or tooling | `AGENTS.md`, `docs/development.md`, relevant package/config files | `docs/deployment.md` unless CI/CD changes |
| Change deployment, Docker, CI/CD, hosting, release flow, rollback, or runtime environment | `AGENTS.md`, `docs/deployment.md`, `docs/configuration.md`, relevant workflow/deployment files | Local-only development docs unless needed |
| Change database schema, migrations, models, external IDs, or data flow | `AGENTS.md`, `docs/architecture.md`, `docs/configuration.md` if env/config is affected, relevant migration/model docs | Deployment docs unless rollout/deploy behavior changes |
| Investigate bugs or incidents | `AGENTS.md`, relevant docs based on affected area, `HANDOFF.md` if present, Critical incidents section in `AGENTS.md` | Unrelated folder-level READMEs |
| Continue unfinished work | `AGENTS.md`, `HANDOFF.md`, relevant docs named inside `HANDOFF.md` | Docs unrelated to the handoff scope |
| Work in a subfolder with its own README | `AGENTS.md`, that folder-level `README.md`, and only broader docs referenced there | Other folder-level READMEs |
| Claude Code session | `CLAUDE.md`, then `AGENTS.md` | Other docs unless task requires them |
| Documentation-only cleanup | `AGENTS.md`, `README.md`, affected docs under `docs/`, folder-level READMEs only where relevant | Source files except as needed to verify accuracy |

`HANDOFF.md` is required reading when it exists. It is temporary continuation context, not canonical architecture.

## Repository structure

Project-owned code:

- `seafile-server/nas-settings/` - Flask admin panel and tests for status, controls, config, libraries, ingest windows, sync schedules, and cached folder-size display.
- `synology-seaf-cli/` - Docker wrapper image for `seaf-cli`, including staging, daemon supervision, status reporter, command dispatcher, schedule enforcement, and folder-size cache scanner.
- `windows-workstation/` - Alternative seaf-cli host for a Windows machine using CIFS source mounts; not active unless explicitly cut over.
- `seafile-server/custom-templates/` - Seahub template overrides for the Microsoft login button and admin-only NAS Sync links.

Docs:

- `README.md` - quick entry point and orientation.
- `AGENTS.md` - canonical AI/developer operating guide and documentation router.
- `CLAUDE.md` - Claude Code-specific instructions only.
- `docs/architecture.md` - system design, components, data flow, constraints.
- `docs/development.md` - local setup, run/test/lint/debug workflow.
- `docs/configuration.md` - environment variables, config files, feature flags.
- `docs/deployment.md` - deploy/release/environment/rollback workflow.
- Folder READMEs: `seafile-server/nas-settings/README.md`, `synology-seaf-cli/README.md`, `seafile-server/custom-templates/README.md`, `windows-workstation/README.md`.
- `HANDOFF.md` - temporary continuation doc only when work is unfinished, blocked, or partially deployed.

Scripts:

- `seafile-server/START_SEAFILE.sh` - VPS pre-flight/start helper.
- `seafile-server/CONFIGURE_OAUTH.sh` - old one-time Google OAuth script; already applied historically and now obsolete for Microsoft SSO. Do not run.
- `seafile-server/CREATE_NAS_SYNC_ACCOUNT.sh` - one-time machine-account script; do not rerun.
- `windows-workstation/setup.ps1` - Windows workstation setup script.

Deployment files:

- `seafile-server/seafile-server.yml`, `seafile-server/caddy.yml`, `seafile-server/nas-settings.yml`.
- `synology-seaf-cli/docker-compose.yml`.
- `windows-workstation/docker-compose.yml`.
- `.github/workflows/seaf-cli-image.yml`, `.github/workflows/nas-settings-image.yml`.

Migrations:

- No project-owned database migrations exist. Seafile owns its MariaDB schemas (`ccnet_db`, `seafile_db`, `seahub_db`).

Generated / third-party / vendor / framework code:

- No vendored source tree is committed. Upstream code lives in images: `seafileltd/seafile-pro-mc:13.0-latest`, `flrnnc/seafile-client:latest`, `mariadb:10.11`, `redis`, and `lucaslorentz/caddy-docker-proxy:2.12-alpine`.

Build artifacts:

- None should be committed. CI publishes images to GHCR; local Python caches and secret dumps are ignored.

## Prime Directive: custom-code boundary

Our custom code lives here:

- `seafile-server/nas-settings/`
- `synology-seaf-cli/`
- `windows-workstation/`
- `seafile-server/custom-templates/`
- `seafile-server/*.yml`
- `seafile-server/*.sh`
- `docs/`
- folder-level `README.md` files
- `.github/workflows/`

Everything else requires justification before touching. Do not edit Seafile's installed upstream files inside containers as the production change. Seahub UI changes belong in `seafile-server/custom-templates/`; runtime config changes must be documented and backed up.

## Core modification inventory

| File | Change made | Why it was necessary | Risk during upgrades |
|---|---|---|---|
| `seafile-server/custom-templates/sysadmin/sysadmin_react_app.html` | Full Seahub template copy with injected admin sidebar link to `/nas-settings/` | Seafile has no plugin hook for adding a custom System Admin page link | Re-diff against the upstream template after Seafile upgrades; a stale copy can break the sysadmin UI |
| `seafile-server/custom-templates/react_app.html` | Full Seahub main app template copy with admin-only NAS Sync sidebar link | Lets admins reach the panel from the main Seafile UI; non-admins do not see a dead admin link | Re-diff after Seafile upgrades; a template syntax error can break the main app page |
| `seafile-server/custom-templates/registration/login.html` | Seahub login template copy with the official Microsoft sign-in button/logo wired to Seafile's SSO click handler | Replaces generic "Single Sign-On" UI with the correct Microsoft SSO affordance | Re-diff after Seafile login template changes; broken markup can affect login |

No upstream source files are modified in-repo; these are runtime template overrides layered through Seafile's custom-template directory.

## Task-to-file navigation: what to edit for common changes

| Task | Files to touch | Files not to touch |
|---|---|---|
| Change login screen | `seafile-server/custom-templates/registration/login.html`, `seafile-server/custom-templates/README.md` | Installed Seahub files inside the `seafile` container |
| Change admin/main NAS Sync links | `seafile-server/custom-templates/sysadmin/sysadmin_react_app.html`, `seafile-server/custom-templates/react_app.html` | Unrelated Seahub templates |
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

## Data model and external identifiers

| Entity/System | Identifier | Where defined | Notes |
|---|---|---|---|
| GitHub repo | `https://github.com/u2giants/seafile` | Git remote | `main` only; no PR branch model documented |
| Public host | `seafile.designflow.app` | `seafile-server/.env.example`, compose labels, live DNS | DNS-only through Cloudflare; do not proxy |
| VPS | `172.233.14.233`, host `seafile-br` | docs/live host | Linode VPS running Seafile and `nas-settings`; do not confuse with other Hetzner/Tailscale hosts that may have stale repo clones |
| NAS | `edgesynology1`, `192.168.3.100` | docs/runtime | Synology NAS; from the VPS use `ssh edge1` as `ai` over Tailscale MagicDNS |
| Microsoft Entra tenant | `1caeb1c0-a087-4cb9-b046-a5e22404f971` | live `seahub_settings.py`, docs | Tenant-locked POP Creations SSO |
| Entra app/client | `8d9da03c-e5cd-4a23-b987-32aaaed31fe7` | live `seahub_settings.py`, docs | Client secret value is not committed |
| Seafile admin account | `4cba3f5721f7436fbe06a2b154ee296a@auth.local` | `ccnet_db.EmailUser`, `seahub_db.profile_profile` | Contact email `albert@popcre.com`; current active admin |
| NAS sync account | `95520c9b8c914cddb93d8d1bf65fa528@auth.local` | `ccnet_db.EmailUser`, `seahub_db.profile_profile` | Contact email `nas-sync@popcre.com`; non-admin machine account |
| Character Licensed library | `177cf9de-3066-482e-956a-7ae8d8786c6d` | `synology-seaf-cli/docker-compose.yml`, `seafile-server/nas-settings/app.py`, database | NAS path `/volume1/mac/Decor/Character Licensed`; owner is current SSO admin |
| Generic Decor library | `1b116ab7-d66b-4411-a691-21f34eadb731` | `synology-seaf-cli/docker-compose.yml`, `seafile-server/nas-settings/app.py`, database | NAS path `/volume1/mac/Decor/Generic Decor`; owner is current SSO admin |
| Styleguides library | `b6e1d4c9-434e-4d8a-bde2-7f19be9c0838` | `synology-seaf-cli/docker-compose.yml` | NAS path `/volume1/styleguides`; synced by the current single NAS `seaf-cli` container |
| ArtLibrary library | `d28d5118-e991-431a-be3d-2e6a15246479` | `synology-seaf-cli/docker-compose.yml`, `seafile-server/nas-settings/app.py`, database | NAS path `/volume1/mac/Art Library`; synced by the current single NAS `seaf-cli` container |
| Current internal public shares | `InnerPubRepo.permission = r` for both NAS libraries | `seafile_db.InnerPubRepo` | Means all logged-in users can read. For read-write, use group/user shares with write permission |
| S3 block bucket | `seafile-s3` | `.env`, `docs/configuration.md` | Linode Object Storage `br-gru-1` |
| S3 commit bucket | `seafile-s3-commits` | `.env`, `docs/configuration.md` | Must remain distinct |
| S3 fs bucket | `seafile-s3-fs` | `.env`, `docs/configuration.md` | Must remain distinct |
| Cloudflare zone | `921eb133a3f7d5802780445b283f84ce` | docs/runtime | Token value is not committed |
| Cloudflare DNS record | `2c1cdc08f9f79d9d668970854d9e15a8` | docs/runtime | DNS-only A record for Seafile host |
| seaf-cli image | `ghcr.io/u2giants/seafile:seaf-cli-latest`, `ghcr.io/u2giants/seafile:sha-<commit>` | `.github/workflows/seaf-cli-image.yml` | CI-built; deploy by pull/recreate |
| nas-settings image | `ghcr.io/u2giants/seafile:nas-settings-latest`, `ghcr.io/u2giants/seafile:nas-settings-sha-<commit>` | `.github/workflows/nas-settings-image.yml` | CI-built; deploy by pull/recreate |

Do not casually rename, regenerate, or replace documented identifiers.

## Container and service inventory

| Container/service | Purpose | Managed by | App/project ID | Image/source |
|---|---|---|---|---|
| `seafile` | Seafile Pro app, Seahub, fileserver | Docker Compose on VPS | none/Coolify not used | `seafileltd/seafile-pro-mc:13.0-latest` |
| `seafile-mysql` | MariaDB metadata database | Docker Compose on VPS | none | `mariadb:10.11` |
| `seafile-redis` | Redis cache/session support | Docker Compose on VPS | none | `redis` |
| `seafile-caddy` | Caddy reverse proxy and TLS | Docker Compose on VPS | none | `lucaslorentz/caddy-docker-proxy:2.12-alpine` |
| `nas-settings` | Flask admin panel and NAS command/status API | Docker Compose on VPS, image from GitHub Actions | none | `ghcr.io/u2giants/seafile:nas-settings-latest` |
| `seaf-cli` | Syncs Character Licensed, Generic Decor, Styleguides, and ArtLibrary NAS folders to Seafile | Docker Compose on `edgesynology1` NAS, or Windows alternative when cut over | none | `ghcr.io/u2giants/seafile:seaf-cli-latest` |

There is no Coolify, Supabase, deploy app ID, or webhook deploy target for this project.

## What to ignore

Do not spend AI context on:

- `.git/`
- `__pycache__/`
- `*.pyc`
- `.env`
- `CREDENTIALS.txt`
- `*.sql`
- `.cache/`
- `coverage/`
- `dist/`
- `node_modules/`
- Build artifacts or generated output if any appear later
- `lucid.md` unless the task is specifically about storage-strategy research

`.claudeignore` and `.cursorignore` must match this section where path ignores apply. `.copilotignore` is absent because this repo has no Copilot-specific ignore need documented.

## Intentional quirks and non-obvious decisions

### Cloudflare proxy disabled

Looks like:
The public host should be behind Cloudflare orange-cloud proxy.

Actually:
`seafile.designflow.app` is DNS-only.

Why:
Seafile desktop sync can use protocols/paths that do not work reliably through Cloudflare's HTTP proxy layer.

Do not change because:
Proxying the record can break desktop sync clients.

### seaf-cli wrapper image

Looks like:
`ghcr.io/u2giants/seafile:seaf-cli-latest` is an unnecessary wrapper around `flrnnc/seafile-client`.

Actually:
The wrapper adds `tini`, fixed process supervision, a correct healthcheck, stale PID/socket cleanup, status reporting, command dispatch, schedule enforcement, and cached folder-size scanning.

Why:
The upstream community image has caused silent sync failures and does not provide this deployment's admin bridge.

Do not change because:
Using the upstream image directly removes production safeguards and the NAS Settings control loop.

### NAS `/library/<key>` paths are live bind mounts

Looks like:
`/library` is a disposable staging volume from the older wrapper design.

Actually:
The current NAS compose bind-mounts live NAS folders directly under `/library/<key>` in the single `seaf-cli` container. The named `seaf-cli-data` volume is only for seaf-daemon state and caches.

Why:
The current wrapper supports multi-library sync directly through `SEAF_LIBRARY_<KEY>` variables and Seafile's exact `seafile-ignore.txt` filename.

Do not change because:
Deleting `/library` paths or treating them as cache can affect live NAS data. To force sync-state rebuilds, operate on `seaf-cli-data` only after an explicit rollback/recovery plan.

### Sync schedule has weekday and weekend windows

Looks like:
The schedule is a single days/start/end block.

Actually:
The panel writes a schedule with separate `weekdays` and `weekends` windows, a shared timezone, and an outer `enabled` flag. The NAS agent still accepts the older one-window shape for backward compatibility.

Why:
Business-hour and off-hour sync needs differ between weekdays and weekends, and overnight windows are common.

Do not change because:
Collapsing the shape back to one window removes the requested granularity and can make existing settings ambiguous.

### `nas-settings` cannot push commands to the NAS

Looks like:
The VPS panel should directly call the NAS.

Actually:
The NAS containers poll `/api/status` every 30 seconds and receive queued commands in the response.

Why:
The VPS cannot reliably reach the NAS, and commands need to route by library UUID rather than ephemeral container hostnames.

Do not change because:
Direct push assumptions break remote operation; hostname-keyed commands can miss the target container.

### `/api/settings` is unauthenticated

Looks like:
The endpoint is missing auth.

Actually:
It intentionally exposes only non-secret library UUID/settings data so NAS containers can poll without a Seafile admin session.

Why:
The NAS agent needs ingest/schedule settings before it can report authenticated status; write/admin endpoints remain protected.

Do not change because:
Adding browser-session auth would break the NAS agent's hourly settings refresh.

### NAS deploy uses SSH from the VPS

Looks like:
GitHub Actions or the NAS MCP should recreate containers after image publish, or the old per-library container names should be managed directly.

Actually:
CI only publishes images. From the VPS, `ssh edge1` logs in to `edgesynology1` as `ai`; Docker requires `sudo -n /var/packages/ContainerManager/target/usr/bin/docker`. The live NAS deployment is the single `seaf-cli` container from `synology-seaf-cli/docker-compose.yml`.

Why:
There is no deploy platform. The `ai` account has a narrow sudoers drop-in for the Synology Docker binary, and old staged files such as `/tmp/seaf-cli-compose.yml` may still describe obsolete per-library containers.

Do not change because:
Using stale two-service compose files or old container names can recreate the wrong topology. Stage the current compose file and verify `docker compose config --services` shows only `seaf-cli` before running `up`.

### Verify the live VPS before deploying

What changed:
On 2026-06-16, a deployment attempt first landed on the wrong host (`root@hetz`, Tailscale IP `100.66.37.58`) where `/worksp/seafile` was a stale repo clone and no Seafile containers existed.

Why:
The live public host resolves to `172.233.14.233` and should identify as `seafile-br`; `/opt/seafile` holds the runtime `.env` and base compose files, while `nas-settings.yml` is deployed from `/home/ai/seafile-repo/seafile-server/nas-settings.yml`.

Future sessions should:
Before running Docker deploy commands, confirm `hostname`, `ls -la /opt/seafile`, and `docker ps` show `seafile`, `seafile-caddy`, and `nas-settings`. If those are absent, stop and find the live VPS instead of adapting commands to the wrong machine.

### seaf-cli failed clone tasks self-heal

What changed:
On 2026-06-11, Character Licensed hit Seafile's "too many files" sync limit and left a failed clone task in `/seafile/seafile-data/clone.db`. Commit `b3436f7` added wrapper cleanup for failed clone tasks before retrying `seaf-cli sync`.

Why:
After the server-side limit was raised, seaf-daemon still returned "Task is already in progress" for the stale failed clone task.

Future sessions should:
Do not delete the `seaf-cli-data` volume for this failure mode. Confirm the server has the intended fileserver limits, then let the current image clear only `state=error` clone rows for the affected repo; active fetch/upload tasks are intentionally left alone.

### 2026-06-19 Generic Decor false-synchronized state

What changed:
Generic Decor drift was traced to Synology host inotify exhaustion, not a stale Seafile index. `seaf-daemon` logged `fail to add watch` / `No space left on device` while the host limit was still `fs.inotify.max_user_watches=8192`; the synced trees contain roughly 541k directories, about 82% of them `@eaDir` thumbnail/metadata junk.

Why:
When directories are not watched, NAS edits there do not fire events, so `seaf-cli status` can report `synchronized` because the client index sees no change. Restarting `seaf-daemon` runs a one-time scan and can temporarily mask the symptom while leaving the inotify limit broken.

Future sessions should:
Do not treat restart as the repair. Raise the Synology host inotify limits persistently via a DSM boot-up task, then deploy the updated `synology-seaf-cli` image. Seafile ignore files must be named exactly `seafile-ignore.txt`; `.seafile-ignore` is not recognized. Ignore rules are cleanup/hygiene and may not reduce inotify watches.

### seaf-cli "bugs" reported against this image are usually base-image bugs, already fixed here

What changed:
A 2026-06 review reported three seaf-cli container bugs — `healthcheck()` always exits 0 (no return), `seaf-daemon` zombie / `tail -f` parking with no restart and no tini, and an unconditional `chown -R seafile:seafile /seafile /library`. Verified against source: all three live in the upstream base image `flrnnc/seafile-client` (its `/entrypoint.sh` and `/home/seafile/entrypoint.py`), NOT in upstream Seafile's `seaf-cli`/`seaf-daemon`, and NOT in this wrapper.

Why:
This image's `Dockerfile` overrides `ENTRYPOINT` to `tini -- /home/seafile/entrypoint.py` (our own `synology-seaf-cli/entrypoint.py`), bypassing the base `/entrypoint.sh` entirely. Our entrypoint already fixes/bypasses all three: `healthcheck()` returns `0/1` and guards a missing rpc socket; `watch()` polls the daemon PID and exits non-zero so Docker restarts it; SIGTERM/SIGINT call `seaf-cli stop`; tini is PID 1; and no `chown -R` runs (no base shell wrapper executes).

Future sessions should:
Do not re-fix those three — they are not present in the running image. Verify against `synology-seaf-cli/entrypoint.py` + `Dockerfile`, not against the `flrnnc/seafile-client` base. The only genuine wrapper bug from that review was the ignore filename/timing (`.seafile-ignore`, written only on first clone), fixed in 8e0f3c8. The real upstream-Seafile defect is separate and unfixed: the worktree monitor (`wt-monitor-linux.c`) adds inotify watches to ignored directories too, so `seafile-ignore.txt` does not reduce inotify watch count.

### seaf-cli deploys ONLY from /volume1/docker/seaf-cli with a .env (2026-06-21 incident)

What changed:
The seaf-cli stack is canonically deployed at `/volume1/docker/seaf-cli/` on edgesynology1 — `docker-compose.yml` (from `synology-seaf-cli/`) + a `.env` (chmod 600) loaded via `env_file:`. It is in Watchtower's watch list (`synology-monitor` `deploy/synology/docker-compose.agent.yml`).

Why:
It had drifted to a personal home dir with creds in a non-auto-loaded `seaf-cli.env`. `sudo docker compose up -d` (no `--env-file`) recreated the container with an empty env — `sudo` strips exported shell vars — so it started with no login (`Bad configuration: SEAF_USERNAME required`) and crash-looped. It was also outside Watchtower's scope, so image fixes never auto-deployed.

Future sessions should:
Never deploy seaf-cli from a home dir or `/tmp`, and never pass creds via shell env + `sudo`. Use the `.env` in the stack dir (`env_file:` fails loud if missing). Keep `seaf-cli` in Watchtower's command list. The repo compose is the source of truth — copy it as-is; do not hand-maintain `-codex`/`-tmp` variants. Full detail in `synology-seaf-cli/README.md` → "2026-06-21 incident".

### Seahub template overrides are full-file copies

Looks like:
Large copied templates should be avoided.

Actually:
They are the only available hook for login-button branding and custom sidebar links.

Why:
Seafile does not expose a plugin slot for these UI changes.

Do not change because:
Editing installed Seahub files would be untracked; removing the overrides removes the only visible panel entry points.

### Folder sizes are cached, not calculated live

Looks like:
The file browser should compute folder sizes when you browse a directory.

Actually:
The NAS agent computes recursive source-folder sizes in the background and reports a cache to the Libraries page.

Why:
Live recursive walks over hundreds of thousands of files and multi-terabyte folders would be slow and disruptive.

Do not change because:
Live folder-size calculation would make browsing expensive and unreliable.

### Microsoft SSO uses internal `@auth.local` usernames

Looks like:
The `@auth.local` accounts are fake users that should be renamed to human emails.

Actually:
They are Seafile internal usernames for SSO-created users; human identity is in profile/contact email and OAuth bindings.

Why:
Seafile's OAuth flow creates internal user IDs and maps external identities separately.

Do not change because:
Renaming internal IDs casually can orphan OAuth bindings, library ownership, or profile rows.

## Credentials and environment

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
| `NAS_STATUS_TOKEN` | Shared NAS status token, passed as `STATUS_TOKEN`/`SEAF_STATUS_TOKEN` | `/opt/seafile/.env` and NAS/Windows env | test value only | yes |
| `SECRET_KEY` | Runtime env inside `nas-settings` | `seafile-server/nas-settings.yml` from `NAS_SETTINGS_SECRET_KEY` | yes for tests | yes |
| `STATUS_TOKEN` | Runtime env inside `nas-settings` | `seafile-server/nas-settings.yml` from `NAS_STATUS_TOKEN` | yes for tests | yes |
| `SEAFILE_INTERNAL_URL` | Internal Seafile URL for admin checks | `seafile-server/nas-settings.yml` | no | yes |
| `SEAFILE_PUBLIC_HOST` | Public host used by panel | `seafile-server/nas-settings.yml` | no | yes |
| `SEAF_SERVER_URL` | Seafile URL for seaf-cli | NAS/Windows compose/env | no | yes |
| `SEAF_USERNAME` | seaf-cli account username | NAS `/tmp/.env` or Windows env | no | yes |
| `SEAF_PASSWORD` | seaf-cli account password | NAS `/tmp/.env` or Windows env | no | yes |
| `SEAF_TOKEN` | Optional seaf-cli auth token alternative | environment only if used | no | optional |
| `SEAF_LIBRARY_<KEY>` | Multi-library UUID mapping; key maps to `/library/<key>` | NAS compose | no | yes |
| `SEAF_LIBRARY` | Legacy single-library UUID; if set, multi-library vars are ignored | Windows/single-library env only | no | optional |
| `SEAF_LIBRARY_UUID` | Legacy seaf-cli library UUID env | code supports legacy | no | no |
| `SEAF_LIBRARY_PASSWORD` | Optional encrypted-library password | environment only if used | no | optional |
| `SEAF_SETTINGS_URL` | Panel settings endpoint for NAS agent | NAS/Windows compose | no | yes |
| `SEAF_STATUS_TOKEN` | NAS agent status token | NAS/Windows env | no | yes |
| `SEAF_UPLOAD_LIMIT` | Optional seaf-cli upload speed cap | environment only if used | no | optional |
| `SEAF_DOWNLOAD_LIMIT` | Optional seaf-cli download speed cap | environment only if used | no | optional |
| `SEAF_SKIP_SSL_CERT` | Optional TLS verification skip | environment only if used | no | optional |
| `SEAF_2FA_SECRET` | Optional TOTP secret for seaf-cli auth | environment only if used | no | optional |
| `DEBUG` | NAS agent debug logging | environment only if used | no | optional |
| `NAS_USERNAME` | Windows CIFS NAS username | Windows workstation env | no | Windows only |
| `NAS_PASSWORD` | Windows CIFS NAS password | Windows workstation env | no | Windows only |
| `GITHUB_TOKEN` | GitHub Actions package publish token | GitHub Actions built-in secret | no | CI only |
| `CF_TOKEN` | Cloudflare DNS API token | operator-provided, not committed | no | only for DNS changes |

Other secret material lives in `/opt/seafile/CREDENTIALS.txt` on the VPS, root-only. Do not paste or commit it.

## Deployment

Real deployment path:

- Branch: `main`.
- CI workflow `seaf-cli image`: `.github/workflows/seaf-cli-image.yml`; runs pyflakes and `synology-seaf-cli/test_entrypoint.py`, then publishes `ghcr.io/u2giants/seafile:seaf-cli-latest` and `ghcr.io/u2giants/seafile:sha-<commit>`.
- CI workflow `nas-settings image`: `.github/workflows/nas-settings-image.yml`; runs pyflakes and `seafile-server/nas-settings/test_app.py`, then publishes `ghcr.io/u2giants/seafile:nas-settings-latest` and `ghcr.io/u2giants/seafile:nas-settings-sha-<commit>`.
- Deploy trigger: manual pull/recreate on the target host after CI succeeds. There is no Coolify, deploy webhook, or app/project ID.
- VPS stack: Docker Compose from `/opt/seafile` plus repo files in `/home/ai/seafile-repo/seafile-server/`.
- `nas-settings` deploy: from `/opt/seafile`, run compose with `--env-file /opt/seafile/.env -f /home/ai/seafile-repo/seafile-server/nas-settings.yml`; do not build on the VPS.
- NAS deploy: SSH from the VPS with `ssh edge1`, stage the current `synology-seaf-cli/docker-compose.yml` as `/tmp/seaf-cli-compose-codex.yml` or another verified current path, rebuild `/tmp/.env` from the running `seaf-cli` container if needed, pull `ghcr.io/u2giants/seafile:seaf-cli-latest`, then run Docker Compose with `sudo -n /var/packages/ContainerManager/target/usr/bin/docker`.
- Rollback: pin the affected service image to an older immutable `sha-<commit>` or `nas-settings-sha-<commit>` tag and recreate.
- Runtime environment variable values live in `/opt/seafile/.env` on the VPS and `/tmp/.env` on the NAS. `/tmp` is wiped on NAS reboot; running containers survive via Docker restart policy, but recreates may need restaging.
- SSH is allowed for manual operator work on VPS/NAS. SSH is not a CI deployment path; GitHub Actions must not SSH to production or run Docker there.

See `docs/deployment.md` for command details.

## Critical incidents

### 2026-06-05 NAS seaf-cli containers found removed

What happened:
The NAS sync containers were absent from `docker ps -a`, so sync had silently stopped.

Impact:
NAS-to-Seafile uploads were not running. No data loss was documented; Seafile libraries, S3 data, and Docker volumes remained.

Root cause:
Unknown. Docker event history did not retain the removal event. Possible manual removal, Synology Container Manager behavior, or NAS maintenance.

Recovery:
Containers were recreated from `synology-seaf-cli/docker-compose.yml`.

Rule added to prevent recurrence:
Verify live container state before documenting sync status; do not trust stale status claims in docs.

### 2026-06-07 SSO admin binding pointed at a duplicate account

What happened:
Microsoft SSO for `albert@popcre.com` landed on a non-admin duplicate account instead of the real admin.

Impact:
The NAS Settings panel and admin-only sidebar link appeared missing because the session was non-admin.

Root cause:
OAuth binding/account churn in `seahub_db.social_auth_usersocialauth`.

Recovery:
The binding was repointed to the admin account and duplicate active users were removed. Current active users are the SSO admin and `nas-sync` machine account.

Rule added to prevent recurrence:
If an SSO duplicate appears, fix the binding and account ownership rather than promoting the duplicate. Verify `EmailUser`, `profile_profile`, and `social_auth_usersocialauth` together.

### 2026-06-07 nas-settings redirected admins because internal URL used Seahub `:8000`

What happened:
Admins visiting `/nas-settings/` were redirected away because the panel's admin-session check could not reach Seahub at `http://seafile:8000`.

Impact:
The panel was unusable even for admins.

Root cause:
Seahub gunicorn binds localhost inside the Seafile container; other containers must reach it through nginx on port 80.

Recovery:
`SEAFILE_INTERNAL_URL` was changed to `http://seafile`.

Rule added to prevent recurrence:
Use the Seafile container's nginx port 80 for internal panel admin checks, not Seahub's localhost-only port 8000.

### 2026-06-08/09 Microsoft OAuth and account cleanup

What happened:
The generic/no-prompt SSO behavior and later duplicate SSO account state required live Seahub config and database cleanup.

Impact:
Incorrect SSO behavior risked insecure login flow or admin landing on the wrong account.

Root cause:
Stale/misconfigured SSO settings and duplicate OAuth bindings/accounts.

Recovery:
Configured Microsoft Entra OAuth, preserved secrets out of output, transferred NAS library ownership to the SSO admin, kept `nas-sync` as the machine account, removed obsolete active users, and made the two NAS libraries internally visible read-only.

Rule added to prevent recurrence:
Back up DB/config before destructive account or ownership changes; keep secrets out of output; document account identities by internal username plus contact email.

## Pending work

| Status | Item | Owner/next action |
|---|---|---|
| open | Decide read-write sharing policy for all users | In GUI, create/use an all-users group and share both NAS libraries read-write; internal public shares are currently read-only |
| open | Onboard POP Creations staff | Users sign in with Microsoft SSO; add them to the read-write group/share policy |
| optional | Move NAS compose/env staging out of `/tmp` | Use a persistent NAS path such as `/volume1/docker/seaf-cli/` if an operator wants easier recreates |
| optional | Windows workstation cutover | Run `windows-workstation/setup.ps1` and stop NAS containers first; only one seaf-cli deployment may run |
| optional | Pin `flrnnc/seafile-client` base image by digest | Improves reproducibility but requires a documented bump procedure |
| optional | Elasticsearch/full-text search | Requires RAM planning; current connection errors are expected because Elasticsearch is not deployed |
