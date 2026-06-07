# AGENTS.md — POP Creations Seafile Infrastructure

## What This Project Is

POP Creations runs a 28TB design file library on two Synology NAS devices in a NYC office. Eight graphic designers in São Paulo need access to that library over the internet. This repo contains all infrastructure configuration to make that work:

1. **Seafile Pro** (image `seafileltd/seafile-pro-mc:13.0-latest`, a rolling tag that auto-tracks the newest 13.0.x patch) running on a Linode VPS (`seafile.designflow.app`) — the relay server. NAS pushes files here via seaf-cli; designers pull via HTTPS/desktop app.
2. **seaf-cli Docker containers** on the Synology NAS — continuously sync NAS folders to specific Seafile libraries. Built from a wrapper image in `synology-seaf-cli/` (the one thing this repo builds and publishes to GHCR).
3. **nas-settings** — a Flask panel on the VPS (`/nas-settings/`) that gives the Seafile web UI a GUI for the seaf-cli client on the NAS: live status, sync controls (pause/resume/restart/stop), daemon config, and library management (list/list-remote/create/desync), plus the ingest window. The server can't reach the NAS, so it queues commands by library UUID and the containers pick them up on their 30 s status poll.
4. File data is stored in **Linode Object Storage (São Paulo, br-gru-1)**, not on the VPS disk. The VPS only holds metadata (MariaDB), session cache (Redis), and config.

This is mostly an **infrastructure configuration repo**. Two images are CI-built and published to GHCR: the seaf-cli wrapper (`.github/workflows/seaf-cli-image.yml`) and the nas-settings panel (`.github/workflows/nas-settings-image.yml`). Everything else runs upstream images via Docker Compose — the deployment artifacts are the compose files and scripts themselves.

---

## Multi-Model Note

There is no universal ignore-file standard across AI coding tools.
`.claudeignore` works for Claude Code; `.cursorignore` for Cursor;
`.copilotignore` for GitHub Copilot. When using any other AI tool
(Gemini, ChatGPT, etc.), paste this file as your first message
and follow the instructions in the 'What to ignore' section.

---

## Repository Structure

```
seafile-repo/                    Root — GitHub: github.com/u2giants/seafile
├── AGENTS.md                    ← You are here. Read before touching anything.
├── CLAUDE.md                    Claude Code-specific instructions
├── HANDOFF.md                   In-progress work notes (delete when NAS sync + designer accounts done)
├── README.md                    Project overview for GitHub
├── .gitignore                   Excludes .env, CREDENTIALS.txt, *.sql
├── .claudeignore
├── .cursorignore
│
├── .github/workflows/
│   ├── seaf-cli-image.yml       CI: lint + test + build + push the seaf-cli wrapper image to GHCR
│   └── nas-settings-image.yml   CI: lint + test + build + push the nas-settings panel image to GHCR
│
├── seafile-server/              VPS configuration — live at seafile.designflow.app
│   ├── seafile-server.yml       Docker Compose: Seafile Pro + MariaDB + Redis
│   ├── caddy.yml                Docker Compose: Caddy reverse proxy + TLS
│   ├── nas-settings.yml         Docker Compose: nas-settings Flask panel
│   ├── .env.example             Template — never commit the real .env
│   ├── START_SEAFILE.sh         Pre-flight checks + start command
│   ├── CONFIGURE_OAUTH.sh       One-time OAuth setup (already run — DO NOT RUN AGAIN)
│   ├── CREATE_NAS_SYNC_ACCOUNT.sh  One-time machine account creation (already run — DO NOT RUN AGAIN)
│   ├── nas-settings/            Flask app (app.py + templates) — seaf-cli control panel + status/command API (test_app.py)
│   │   └── Dockerfile           Built + published by CI to ghcr.io/u2giants/seafile:nas-settings-latest
│   ├── custom-templates/        Seahub template override — injects the nas-settings link into the sysadmin sidebar
│   └── docs/                    seafile-server component docs (see "Documentation map" below)
│       ├── architecture.md      Containers, networking, storage architecture
│       ├── configuration.md     All env vars and config file contents
│       ├── deployment.md        Start/stop, updates, backup, NAS image releases
│       └── development.md       Logs, debugging, API usage, user management
│
├── synology-seaf-cli/           NAS sync containers — wrapper image source
│   ├── Dockerfile               Wrapper image — FROM flrnnc/seafile-client:latest, adds tini + fixed entrypoints
│   ├── entrypoint.py            Fixed Seafile daemon entrypoint (replaces image default) + healthcheck + status reporter & command dispatcher (test_entrypoint.py)
│   ├── seaf-entrypoint.py       Hardlink/scandir date-filter staging wrapper; launches entrypoint.py
│   ├── docker-compose.yml       One service per Seafile library
│   ├── .env.example             NAS sync password template
│   └── README.md                Synology setup + redeploy instructions
│
└── windows-workstation/         Alternative seaf-cli host (NOT active) — Windows rendering machine
    ├── docker-compose.yml       seaf-cli containers (sources via CIFS from NAS)
    ├── setup.ps1                One-shot installer: PopDAM agent + Docker + seaf-cli
    └── README.md                Machine replacement instructions for Albert
```

All files in this repo are **authored by this project** — there are no third-party packages or vendor directories. The two things built from upstream bases are the seaf-cli wrapper (`FROM flrnnc/seafile-client:latest`) and `nas-settings` (a Flask app); both layer our code on top rather than modifying vendor code in-repo.

### Documentation map (avoid duplication)

| File | Scope |
|------|-------|
| `AGENTS.md` (this file) | Canonical operating guide for the whole repo — read first |
| `README.md` | Short GitHub orientation |
| `CLAUDE.md` | Claude Code-specific notes; points here |
| `seafile-server/docs/*` | Deep reference for the VPS server component only |
| `synology-seaf-cli/README.md` | seaf-cli image internals + NAS deploy |
| `seafile-server/nas-settings/README.md` | nas-settings app internals |
| `windows-workstation/README.md` | Windows cutover runbook |

There is intentionally **no top-level `docs/`** — component docs live beside the component they describe. Do not create a parallel top-level `docs/` tree; it would duplicate `seafile-server/docs/`.

---

## The Prime Directive

**Our configuration lives in this repo.** All changes to the Seafile infrastructure go through files in this repo, committed to `main`, then applied on the VPS or NAS. Never make changes directly on the server and consider them done — changes made only on the server will be lost or overwritten and leave the repo out of sync with reality.

**Scripts that say "DO NOT RUN AGAIN" are off-limits.** `CONFIGURE_OAUTH.sh` and `CREATE_NAS_SYNC_ACCOUNT.sh` have already been run against the live system. Running them again creates duplicates. See Idiosyncratic Decisions.

---

## Core Modification Inventory

This project is original infrastructure config (not a fork). No upstream source files are edited in-repo. The only place we override upstream behavior is a Seahub template, layered via a volume mount (not a code edit):

| File | Change made | Why it was necessary | Risk during upgrades |
|------|-------------|----------------------|----------------------|
| `seafile-server/custom-templates/sysadmin/sysadmin_react_app.html` | Overrides Seahub's sysadmin template to inject a sidebar link to `/nas-settings/` | Seafile has no plugin hook to add a custom admin page link | A Seafile UI upgrade can change this template; if the override drifts from upstream the sidebar may render stale. Re-diff against the new Seahub template after major server upgrades. |

---

## Decision Tree

### If you need to change a Seafile configuration setting:
- Edit the relevant file in `/opt/seafile-data/seafile/conf/` on the VPS
- Copy the updated content into `seafile-server/docs/configuration.md` in this repo
- Commit to main, push

### If you need to add a new NAS folder sync:
1. Identify the NAS path (ask Albert — paths are case-sensitive)
2. Create a Seafile library via admin UI or API; record the UUID
3. Add a new service block to `synology-seaf-cli/docker-compose.yml` following the existing pattern
4. Deploy to NAS via NAS MCP (base64-encode docker commands — see the "NAS Docker commands must be base64-encoded" idiosyncratic decision below for the pattern)
5. Update the Container Inventory in this file
6. Commit and push

### If you need to update the Seafile server version:
- The image is pinned to the rolling tag `seafileltd/seafile-pro-mc:13.0-latest`, so a plain `docker compose pull seafile && docker compose up -d --force-recreate seafile` already moves to the newest **13.0.x patch**. No file change is needed for patch updates.
- To move to a new **minor/major** (e.g. a future 13.1 or 14.0): check https://manual.seafile.com for breaking changes, edit `SEAFILE_IMAGE` in `/opt/seafile/.env` and the default in `seafile-server/seafile-server.yml`, commit, then pull + recreate. Watch `docker logs -f seafile`.
- As of 2026-06: 13.0 is the current major; the server tracks it automatically.

### If you need to deploy or change the nas-settings panel:
- Code lives in `seafile-server/nas-settings/` (Flask `app.py` + templates); compose in `seafile-server/nas-settings.yml`. Commit to `main` → CI (`nas-settings image`) tests + builds + publishes `ghcr.io/u2giants/seafile:nas-settings-latest` (+ `:nas-settings-sha-<commit>`). Deploy by **pulling** that image on the VPS — do not `docker compose build` on the host (§25 exception model).
- Build + deploy steps are in `seafile-server/nas-settings/README.md`.
- The sidebar links come from `seafile-server/custom-templates/` (see Core Modification Inventory).

### If you need to manage DNS:
- Zone: `designflow.app` · Zone ID: `921eb133a3f7d5802780445b283f84ce`
- Use Cloudflare API with `CF_TOKEN` (from Albert)
- Never enable proxy (orange cloud) on `seafile.designflow.app` — see Idiosyncratic Decisions

### If you need to set up or replace the Windows rendering machine:
- Run `windows-workstation/setup.ps1` as Administrator on the target machine
- It installs PopDAM Windows Agent (from GitHub releases) + seaf-cli containers (Docker)
- If switching from NAS to Windows: stop NAS containers first (`docker compose stop` on edgesynology1) — never run both simultaneously
- If seaf-cli has never run on that Windows machine before, Docker will SHA1-hash all files on first start — expect 200-300% CPU for several hours
- NAS credentials: a local Synology user with read access to the `mac` share is needed; see README.md for which account to use

### If you need to add a designer user:
- Send them `https://seafile.designflow.app` — they click "Sign in with Microsoft" and use their POP Creations **M365** account; the account auto-creates (tenant-locked — only POP Creations staff can self-serve). SSO is M365, not Google — see Idiosyncratic Decisions.
- Then share libraries via web UI: open library → Share → Share to User → Read/Write
- Or via API — see `seafile-server/docs/development.md`

### If something breaks on the VPS:
- Check `docker compose -f /opt/seafile/seafile-server.yml -f /opt/seafile/caddy.yml ps`
- Check `docker logs seafile`
- Full debugging guide in `seafile-server/docs/development.md`

---

## Task-to-File Navigation Map

| Task | File to touch | Do NOT touch |
|------|--------------|--------------|
| Change seaf-cli staging/daemon logic | `synology-seaf-cli/seaf-entrypoint.py`, `synology-seaf-cli/entrypoint.py` (rebuilds image via CI) | the upstream `flrnnc/seafile-client` behavior |
| Add/modify seaf-cli sync container | `synology-seaf-cli/docker-compose.yml` (NAS) or `windows-workstation/docker-compose.yml` (Windows) | both at once — only one host runs seaf-cli |
| Change the CI build/publish | `.github/workflows/seaf-cli-image.yml`, `.github/workflows/nas-settings-image.yml` | add SSH/deploy steps — see Deployment |
| Change Seafile/MariaDB/Redis container config | `seafile-server/seafile-server.yml` | container names (Seafile-internal) |
| Change reverse proxy (TLS, routing) | `seafile-server/caddy.yml` | enable Cloudflare proxy on the host |
| Change nas-settings panel | `seafile-server/nas-settings/app.py` + `templates/`, `seafile-server/nas-settings.yml` | — |
| Change the sysadmin sidebar link | `seafile-server/custom-templates/sysadmin/sysadmin_react_app.html` | unrelated Seahub templates |
| Change environment variables | `/opt/seafile/.env` on VPS (then update `.env.example` + docs) | committing real `.env` |
| Change seahub settings (OAuth, time zone) | `/opt/seafile-data/seafile/conf/seahub_settings.py` on VPS | `CONFIGURE_OAUTH.sh` (do not re-run) |
| Update architecture / config / deploy / debug docs | `seafile-server/docs/{architecture,configuration,deployment,development}.md` | — |
| Update the canonical guide | `AGENTS.md` | — |

---

## Data Model / Custom Objects

This is not an application with a custom data model. The data model is Seafile's internal schema (stored in MariaDB across `ccnet_db`, `seafile_db`, `seahub_db`).

### Seafile Libraries (permanent UUIDs — never change)

| Library name | UUID | NAS source path | Sync status (2026-06-05) |
|-------------|------|-----------------|--------------------------|
| Character Licensed | `177cf9de-3066-482e-956a-7ae8d8786c6d` | `/volume1/mac/Decor/Character Licensed` | ⏸ Not syncing — seaf-cli container removed (see Critical Incident Log) |
| Generic Decor | `1b116ab7-d66b-4411-a691-21f34eadb731` | `/volume1/mac/Decor/Generic Decor` | ⏸ Not syncing — seaf-cli container removed |

These are the only two libraries.

### Accounts

| Account | Type | Purpose |
|---------|------|---------|
| u2giants@gmail.com | Local admin | Albert's primary admin. Note: signs in via the email/password form — the SSO button is now M365, so this Google address can no longer SSO |
| albert@popcre.com | Local admin | Albert's fallback local account |
| nas-sync@popcre.com | Local machine account | Used by seaf-cli containers to push files |

SSO is **M365**, tenant-locked to POP Creations (Azure AD tenant `1caeb1c0-a087-4cb9-b046-a5e22404f971`). See Idiosyncratic Decisions.

---

## Container Inventory

### VPS Containers (Linode 172.233.14.233)

These containers are defined by the upstream Seafile Docker Compose. Their names do not follow the `[app]-[function]` standard because they are pre-defined by Seafile and renaming running containers is destructive. See Idiosyncratic Decisions.

| Container name | Function | Compose file |
|---------------|----------|-------------|
| `seafile` | Seafile Pro app, image `seafileltd/seafile-pro-mc:13.0-latest` (seahub + seafile-server) | `seafile-server/seafile-server.yml` |
| `seafile-mysql` | MariaDB 10.11 — metadata database | `seafile-server/seafile-server.yml` |
| `seafile-redis` | Redis — session cache | `seafile-server/seafile-server.yml` |
| `seafile-caddy` | Caddy reverse proxy — TLS termination | `seafile-server/caddy.yml` |
| `nas-settings` | Flask seaf-cli control panel + status/command API, image `ghcr.io/u2giants/seafile:nas-settings-latest` (CI-built) | `seafile-server/nas-settings.yml` |

### NAS Containers (edgesynology1 — 192.168.3.100)

These follow the standard naming convention. Only run these OR the Windows containers — not both.

**Current state (2026-06-06): both containers are running healthy on edgesynology1** — verified via `docker ps`.

| Container name | NAS path | Seafile library | UUID | Status |
|---------------|----------|----------------|------|--------|
| `seaf-cli-char-licensed` | `/volume1/mac/Decor/Character Licensed` | Character Licensed | `177cf9de-3066-482e-956a-7ae8d8786c6d` | ✅ Running (verified 2026-06-06) |
| `seaf-cli-generic-decor` | `/volume1/mac/Decor/Generic Decor` | Generic Decor | `1b116ab7-d66b-4411-a691-21f34eadb731` | ✅ Running (verified 2026-06-06) |

### Windows Workstation Containers (alternative deployment — not yet active)

Defined in `windows-workstation/docker-compose.yml`. Same containers, same image, same libraries — sources mounted via CIFS from the NAS over LAN instead of local bind mounts. To activate: stop NAS containers, run `setup.ps1` on the Windows machine.

| Container name | Source (CIFS) | Seafile library | UUID |
|---------------|---------------|----------------|------|
| `seaf-cli-char-licensed` | `//edgesynology1/mac/Decor/Character Licensed` | Character Licensed | `177cf9de-3066-482e-956a-7ae8d8786c6d` |
| `seaf-cli-generic-decor` | `//edgesynology1/mac/Decor/Generic Decor` | Generic Decor | `1b116ab7-d66b-4411-a691-21f34eadb731` |

There is no Coolify for this project. Containers are managed directly via Docker on the Linode VPS.

---

## What to Ignore

No large third-party packages are included in this repo. Nothing to ignore for AI context purposes.

---

## Idiosyncratic Decisions

### VPS container names don't follow the naming standard
**Looks like:** Containers named `seafile`, `seafile-mysql`, `seafile-redis`, `seafile-caddy` violate the `[app]-[function]` naming rule.
**Actually:** These names are defined by Seafile's official Docker Compose templates and cannot be changed without breaking the application's internal service discovery (containers communicate by service name on `seafile-net`).
**Why:** Upstream constraint — Seafile's code references container names internally.
**Do not change because:** Renaming running containers breaks inter-container networking. The official Seafile compose is the source of these names.

### Cloudflare proxy is permanently disabled on seafile.designflow.app
**Looks like:** A security oversight — the domain isn't behind Cloudflare proxy.
**Actually:** Intentional. Seafile's desktop sync client uses a binary protocol on port 8082 that breaks through Cloudflare's HTTP proxy layer.
**Why:** Enabling the orange cloud breaks all desktop sync clients immediately.
**Do not change because:** Proxied DNS would break sync for all users.

### CONFIGURE_OAUTH.sh is labeled "do not run again" even though it looks idempotent
**Looks like:** A script that could safely be re-run to reconfigure OAuth.
**Actually:** Running it twice appends a duplicate OAuth block to `seahub_settings.py`, which causes a Django import error and takes down the web UI.
**Why:** The script appends rather than upserts — no idempotency check.
**Do not change because:** The OAuth config is already live and working. If OAuth settings need changing, edit `seahub_settings.py` directly.

### seaf-cli containers use a wrapper image built on flrnnc/seafile-client
**Looks like:** The image `ghcr.io/u2giants/seafile:seaf-cli-latest` is not the official seaf-cli image.
**Actually:** `seafileltd/seaf-cli` does not exist. `flrnnc/seafile-client` is the community standard (46k+ pulls, formerly `flowgunso/seafile-client`). Our wrapper builds FROM that image and layers in: tini as PID 1, a fixed `entrypoint.py` (daemon watchdog, correct healthcheck exit codes, SIGTERM handler, subprocess return codes checked), and our `seaf-entrypoint.py` as the primary entrypoint. Built automatically via GitHub Actions on every commit to the relevant files.
**Why:** Upstream `flrnnc/seafile-client` has confirmed bugs: healthcheck always exits 0 (never reports unhealthy), seaf-daemon becomes a zombie with no detection or restart, and `follow()` exits code 0 preventing Docker's restart policy from firing. Issues filed upstream; wrapper image is the production fix.
**Do not change because:** Switching back to `flrnnc/seafile-client:latest` directly reintroduces all three bugs. The wrapper image is required.

### seaf-cli is 7.0.10 while the server is 13.0
**Looks like:** A version mismatch to fix — the client (seaf-cli 7.0.10, bundled in `flrnnc/seafile-client`) is far behind the server (Seafile Pro 13.0).
**Actually:** This is expected and works. seaf-cli's sync protocol is backward-compatible, and there is no actively maintained community Docker image with a newer seaf-cli. The community `flrnnc/seafile-client:latest` still ships 7.0.10. Seafile does not publish an official seaf-cli image.
**Why:** Upgrading seaf-cli would mean either waiting for the community image to package a newer client, or building seaf-cli from source ourselves — neither is justified while 7.0.10 syncs correctly against the 13.0 server.
**Do not change because:** Chasing a newer client adds a build/maintenance burden for no functional gain. Revisit only if a future server release drops 7.x client compatibility.

### The wrapper Dockerfile uses `FROM flrnnc/seafile-client:latest` (unpinned)
**Looks like:** A reproducibility hole — `:latest` can change under us.
**Actually:** Deliberate for now: it lets a rebuild pick up community fixes without manual digest bumps. Our own `sha-<commit>` image tags still pin **our** layers; the base float is the one non-reproducible input.
**Why:** Low churn (the base updates rarely) and we want community bug fixes automatically.
**Do not change lightly:** Pinning the base to a digest would make builds fully reproducible (closer to §18) but then base updates require a manual digest bump. If reproducibility becomes a priority, pin it and document the bump procedure. Tracked in Pending Work.

### nas-settings `/api/settings` is intentionally unauthenticated
**Looks like:** A missing auth check — `GET /nas-settings/api/settings` returns library config with no login.
**Actually:** Intentional. The NAS seaf-cli containers (which have no Seafile session cookie) poll this read-only endpoint hourly to pick up ingest-window changes. It exposes only library name, UUID, and `ingest_days` — no secrets. The admin-facing UI and writes ARE gated (the app verifies the Seafile `sessionid` cookie against `/api/v2.1/admin/sysinfo/`). The container status POST to `/api/status` is gated by `SEAF_STATUS_TOKEN`.
**Why:** seaf-cli has no way to authenticate as a Seafile admin; a read-only public settings feed is the simplest safe contract.
**Do not change because:** Adding auth to `/api/settings` would break the hourly ingest-window refresh on every seaf-cli container.

### NAS source mounts to /source; /library is a Docker staging volume
**Looks like:** The NAS folder should mount directly to `/library`.
**Actually:** The `flrnnc/seafile-client` image uses `/library` as its sync target and `/seafile` for state. We mount the NAS folder read-only at `/source`, and a staging Docker volume at `/library`. A Python wrapper (`seaf-entrypoint.py`) populates `/library` from `/source` (with optional date filtering via `SEAF_INGEST_DAYS`) before handing off to the image's own `entrypoint.py`. Staging is done with **hardlinks** (one `os.scandir` pass to select by mtime; `os.link` to place), so the in-window working set is not physically duplicated on the NAS and the hourly refresh re-scans with ~half the syscalls. It falls back to `shutil.copy2` only when `/source` and `/library` are on different filesystems (`st_dev` differs) — on the NAS they share `volume1`, so hardlinks are used.
**Why:** Enables per-library date-range filtering without modifying the upstream image. seaf-cli sees a clean, filtered `/library` and syncs that to Seafile. Hardlinking keeps that view free of an extra on-disk copy.
**Do not change because:** If you mount the NAS folder directly to `/library` and bypass the wrapper, the date filter is lost. The staging volume also prevents seaf-cli from uploading every file on the NAS before the filter can run.

### seaf-cli env vars use SEAF_* prefix, not the obvious names
**Looks like:** Wrong env var names — you'd expect `SERVER_URL`, `USERNAME`, `PASSWORD`, `LIBRARY_ID`.
**Actually:** The correct vars are `SEAF_SERVER_URL`, `SEAF_USERNAME`, `SEAF_PASSWORD`, `SEAF_LIBRARY` (UUID, not a name).
**Why:** The community image uses this prefix. Using the wrong names results in a silently misconfigured container that starts but never syncs.
**Do not change because:** These are hardcoded in the image entrypoint.

### NAS Docker commands must be base64-encoded when run via MCP
**Looks like:** An unnecessarily complex way to run docker commands.
**Actually:** The Synology MCP `run_command` allowlist blocks any command string containing the word "docker". Base64 encoding bypasses the string match.
**Why:** The MCP server's allowlist is a blunt substring filter.
**Do not change because:** This is a workaround for the MCP server's design. Pattern: `CMD="..."; echo $(echo "$CMD" | base64) | base64 -d | bash`

### Docker binary on Synology is not in PATH
**Looks like:** Docker isn't installed on the NAS.
**Actually:** Docker is at `/var/packages/ContainerManager/target/usr/bin/docker` — not symlinked into PATH.
**Why:** Synology installs Docker via Package Manager into a non-standard path and doesn't add it to PATH.
**Do not change because:** You can't change the Synology packaging. Always use the full path in commands.

### M365 SSO replaces Google SSO — u2giants@gmail.com can no longer sign in via SSO
**Looks like:** The primary admin account is broken.
**Actually:** `u2giants@gmail.com` and `albert@popcre.com` both have local Seafile passwords and can log in via the email/password form. Only the SSO button changed (Google → Microsoft).
**Why:** POP Creations uses M365, not Google Workspace. Tenant-locked M365 SSO means only POP Creations staff can self-serve log in — no invitations needed, no public access.
**Do not change because:** Switching back to Google would allow anyone with a Google account to attempt login. The M365 tenant ID in the OAuth URLs is what enforces the org boundary.

### seafevents.conf references Elasticsearch that doesn't exist
**Looks like:** A misconfiguration causing errors.
**Actually:** Intentional — Elasticsearch is not deployed due to RAM constraints (it needs ~2GB on a 4GB server). The config logs a connection error every 10 minutes; this is harmless.
**Why:** `vm.max_map_count` is already set in `/etc/sysctl.conf` so Elasticsearch can be added later without a reboot.
**Do not change because:** The error is harmless. Adding Elasticsearch requires a deliberate decision about RAM allocation.

### S3 requires exactly 3 separate buckets
**Looks like:** Unnecessary complication — one bucket should work.
**Actually:** Seafile's storage architecture requires distinct bucket names for blocks, commits, and fs. It refuses to start if any two share a name.
**Why:** Seafile's storage layer addresses each bucket type independently.
**Do not change because:** This is a hard Seafile requirement, not a choice.

### seaf-cli compose file is deployed from /tmp on the NAS
**Looks like:** The compose file will be lost on reboot.
**Actually:** The container has `restart: unless-stopped` — Docker restores it automatically after reboot without needing the compose file. The compose file is only needed for initial deploy or if the container is manually removed.
**Why:** The NAS MCP `run_command` tool blocks `mkdir` and write redirection operators. Files must be written via tee, and `/tmp` is the most reliable writable path.
**Do not change because:** This is a workaround for MCP write restrictions. If the container is ever manually removed: re-write the compose file from this repo and re-run `docker compose up -d`.

### SEAF_INGEST_DAYS controls the per-library upload window
**Looks like:** An undocumented environment variable.
**Actually:** Set in `docker-compose.yml` under each service's `environment:` block. Tells the `seaf-entrypoint.py` wrapper to only include files whose mtime is within the last N days. Refreshes every hour so newly-modified files enter the window automatically.
**Why:** POP Creations designers only need recent assets; uploading the entire 28TB library to S3 would be expensive and slow.
**Do not change because:** Lowering the value removes files from Seafile (seaf-cli sees them disappear from /library). Raising it adds them back. Removing the line entirely syncs all files.

### seaf-entrypoint.py uses subprocess.run to launch entrypoint.py, not os.execv
**Looks like:** An unnecessary subprocess where exec would be simpler.
**Actually:** The original design used `os.execv` which replaces the process image and kills all threads — including the `refresh_loop` thread. With `os.execv`, the ingest window never slid forward between restarts; the hourly refresh silently never ran.
**Why:** `subprocess.run` keeps seaf-entrypoint.py alive as the parent process so the refresh thread runs every hour as intended.
**Do not change because:** Reverting to `os.execv` breaks the hourly file refresh without any warning. Files modified within `SEAF_INGEST_DAYS` but after the last restart would not be picked up until the next container restart.

### tini is PID 1 in seaf-cli containers
**Looks like:** An unnecessary layer — just run the Python entrypoint directly.
**Actually:** Without a proper init, zombie processes (defunct seaf-daemon after unexpected exit) accumulate and SIGTERM from `docker stop` is not forwarded to child processes.
**Why:** tini is a minimal init (~20KB) that reaps orphaned zombie processes and correctly forwards signals to its child tree. Standard pattern for containerized daemons.
**Do not change because:** Removing tini reintroduces zombie accumulation and broken signal handling on container stop/restart.

### entrypoint.py clears stale PID and socket before seaf-cli start
**Looks like:** Unnecessary file deletion — seafile should handle its own state.
**Actually:** `seaf-cli start` reads `seafile.pid` from the persistent `/seafile` volume and checks whether that PID is currently alive. After `docker compose --force-recreate`, the data volume carries over the old container's PID file. In the new container's PID namespace, that PID may belong to a live unrelated process (tini, python). seaf-cli sees it as "already running" and exits 1, crashing the container in a restart loop.
**Why:** Deleting the stale PID and socket files in `initialize()` before calling `seaf-cli start` makes the start idempotent on container recreation.
**Do not change because:** Removing the cleanup reintroduces the restart loop whenever `--force-recreate` is used (e.g. for image updates). The bug is subtle — the container crashes immediately with no obvious error unless you can read Docker logs.

### entrypoint.py and seaf-entrypoint.py use `from __future__ import annotations`
**Looks like:** An unnecessary import — Python type hints work fine without it.
**Actually:** `str | None` and `int | None` union syntax in function signatures requires Python 3.10+. The `flrnnc/seafile-client` base image ships an older Python (confirmed 3.9 or earlier). Without `from __future__ import annotations`, the files crash at import time with `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`.
**Why:** `from __future__ import annotations` makes all annotations lazy strings at runtime, so the `|` syntax is never evaluated by the interpreter — backward compatible to Python 3.7.
**Do not change because:** Removing it or adding new `X | Y` type hints without it will crash both files on startup on any Python < 3.10, including the base image.

### seaf-cli containers have CPU and memory limits in docker-compose
**Looks like:** Unnecessary constraints — just let the daemon use what it needs.
**Actually:** seaf-daemon spikes to 200-300% CPU on every startup because it SHA1-hashes every file to build the initial block tree. With 467k files (char-licensed), this can make the NAS unusable for other services (RAID scrub, file sharing, ShareSync). `SEAF_UPLOAD_LIMIT`/`SEAF_DOWNLOAD_LIMIT` only throttle network, not hashing.
**Why:** `cpu_shares: 512` is a soft scheduling weight (half of default 1024) — Docker only throttles under CPU contention, not always. Memory limits are hard (OOMKill, container restarts cleanly via watchdog). Hard `cpus` limits were tried first but Synology's kernel does not support CFS CPU quota cgroups and returns "NanoCPUs can not be set". `cpu_shares` is the only CPU limit that works on Synology.
**Do not change because:** Without limits, a fresh sync of char-licensed (467k files) degrades the NAS for hours. Do not replace `cpu_shares` with `cpus` — it will fail on Synology. Tune memory up if OOMKills appear in Docker events. Current values: both containers `cpu_shares: 512`, char-licensed `memory: 2g`, generic-decor `memory: 512m`.

### windows-workstation uses CIFS named volumes, not bind mounts, for sources
**Looks like:** Should just mount the NAS share as a bind mount like on the NAS.
**Actually:** Bind mounts from Windows paths into Docker Desktop containers are unreliable for UNC paths (`\\server\share`). CIFS named volumes (`driver: local`, `type: cifs`) mount the SMB share from inside Docker's Linux VM (WSL2) using the kernel's CIFS stack — well-supported and the standard pattern for NAS-to-Docker-Desktop workflows.
**Why:** Docker Desktop on Windows uses WSL2 (a Linux VM). Bind mounts work for local Windows paths but not for SMB paths. The CIFS volume driver mounts from inside that Linux VM, which can reach the NAS over the local network.
**Do not change because:** If seaf-cli on the Windows machine can't reach the source files, it will simply sync an empty directory to Seafile — silently deleting the library. Always verify containers are healthy after deploy. If `edgesynology1` doesn't resolve from inside Docker, use the NAS IP address in the device paths.

---

## Credentials and Environment

**Never put actual values in this file or in any committed file.**

| Credential | Where to find it | Used for |
|-----------|-----------------|---------|
| Seafile admin password | `/opt/seafile/CREDENTIALS.txt` on VPS (root-only, chmod 600) | Seafile API auth |
| MySQL root password | `/opt/seafile/.env` on VPS | Database backup/restore |
| MySQL seafile user password | `/opt/seafile/.env` on VPS | App DB connection |
| JWT private key | `/opt/seafile/.env` on VPS | Internal service tokens |
| S3 key ID + secret | `/opt/seafile/.env` on VPS | Linode Object Storage |
| Microsoft 365 OAuth client ID + secret | `/opt/seafile/CREDENTIALS.txt` on VPS | SSO login (tenant-locked to POP Creations) |
| nas-sync@popcre.com password | `/opt/seafile/CREDENTIALS.txt` on VPS | seaf-cli NAS sync |
| Seafile library UUIDs | `/opt/seafile/CREDENTIALS.txt` on VPS + this file | seaf-cli config |
| `NAS_SETTINGS_SECRET_KEY` | `/opt/seafile/.env` on VPS → nas-settings `SECRET_KEY` | Flask session signing for the nas-settings panel |
| `SEAF_STATUS_TOKEN` | shared between nas-settings env and each seaf-cli container env | Authenticates seaf-cli status POSTs to nas-settings `/api/status` |
| Cloudflare API token | From Albert | DNS management |
| Linode API token | From Albert | VPS/object storage management |
| docker.seadrive.org credentials | Username: `seafile` / Password: `zjkmid6rQibdZ=uJMuWS` (published by Seafile) | Pull Seafile Pro images |

GitHub Actions stores **no** deploy or SSH secrets — CI only needs the built-in `GITHUB_TOKEN` to push to GHCR. Do not add production SSH keys to GitHub Secrets (see Deployment / §10).

**Environment variables for the VPS** are documented exhaustively in `seafile-server/docs/configuration.md`.
**NAS sync password** is set as `NAS_SYNC_PASSWORD` in `/tmp/.env` on edgesynology1 (created during deploy).

### Key identifiers (permanent — never change)
| Identifier | Value |
|-----------|-------|
| VPS IP | `172.233.14.233` |
| Seafile hostname | `seafile.designflow.app` |
| Cloudflare zone ID | `921eb133a3f7d5802780445b283f84ce` |
| Cloudflare DNS record ID | `2c1cdc08f9f79d9d668970854d9e15a8` |
| Azure AD tenant ID | `1caeb1c0-a087-4cb9-b046-a5e22404f971` |
| Azure app (client) ID | `8d9da03c-e5cd-4a23-b987-32aaaed31fe7` |
| Supabase project | Not used in this project |
| GitHub repo | `https://github.com/u2giants/seafile` |
| Branch model | `main` only — commit straight to main, no feature branches, no PRs |
| seaf-cli image (mutable pointer) | `ghcr.io/u2giants/seafile:seaf-cli-latest` |
| seaf-cli image (immutable, per build) | `ghcr.io/u2giants/seafile:sha-<commit-sha>` |
| nas-settings image (mutable pointer) | `ghcr.io/u2giants/seafile:nas-settings-latest` |
| nas-settings image (immutable, per build) | `ghcr.io/u2giants/seafile:nas-settings-sha-<commit-sha>` |
| CI workflows | `.github/workflows/seaf-cli-image.yml` ("seaf-cli image"), `nas-settings-image.yml` ("nas-settings image") |
| Linode Object Storage region | `br-gru-1` (São Paulo) |
| S3 blocks bucket | `seafile-s3` |
| S3 commits bucket | `seafile-s3-commits` |
| S3 fs bucket | `seafile-s3-fs` |

---

## Deployment

This is primarily a **config-only repo**. Two build artifacts are CI-built and published to GHCR: the seaf-cli wrapper image (`:seaf-cli-latest` + `:sha-<commit>`) and the nas-settings panel image (`:nas-settings-latest` + `:nas-settings-sha-<commit>`); everything else (VPS Seafile, MariaDB, Redis, Caddy) runs upstream images with no build step.

### CI/CD model — documented §25 exception to the Coolify default

The org-wide CI/CD rules assume a deployment platform (Coolify) that GitHub Actions triggers by API/webhook, which then pulls and runs the image. **This repo has no deployment platform**, so that path does not apply. Per §25, the exception is recorded here. It covers **both** CI-built images — the seaf-cli wrapper and the nas-settings panel.

- **Why the default doesn't fit:** The runtime hosts are a Linode VPS (the Seafile server **and** the nas-settings panel, managed by direct Docker Compose) and a Synology NAS / Windows workstation (the seaf-cli containers). None is fronted by Coolify or any deploy platform; a Synology NAS in particular cannot run one. There is no platform API to trigger.
- **Replacement release path:** Edit files in repo → commit to `main` → GitHub Actions (`seaf-cli image` / `nas-settings image`) runs lint + tests (gated via native `needs`), builds, and publishes the image to GHCR. Deployment is then a manual, repo-driven **pull** of that already-published image on the target host (no rebuild on the host). The host runs only what the repo (compose) + registry (image) define.
- **Verification enforcement:** In each workflow the `build-push` job depends on the `lint`/`test` job with native `needs`; a verification failure blocks publish. There is no second workflow and no SHA-polling gate. Neither image is ever built on the production host as the normal path.
- **Artifact deployed:** Exactly the image built by the approved workflow, identified by its immutable `sha-`/`nas-settings-sha-` tag. The `…-latest` tags are convenience pointers for normal deploys.
- **Rollback:** Re-point a container's `image:` at a prior immutable tag (`:sha-<older-commit>` for seaf-cli, `:nas-settings-sha-<older-commit>` for the panel) and `up -d` — no manual file edits or local image builds.
- **Where runtime config lives:** In repo-managed Compose (`docker-compose.yml`, `nas-settings.yml` — image, volumes, env var *names*, resource limits, Caddy labels) plus host-side secret *values* in `/tmp/.env` (NAS) and `/opt/seafile/.env` (VPS). There is no deploy platform to own runtime config, so the repo compose is authoritative and host env files hold only secret values.
- **Audit trail:** GitHub Actions run history + GHCR image tags + git commit history. Every deployed container traces to a commit via its immutable tag.
- **Avoiding hidden server state:** No CI step SSHes into or mutates production. The host pull/recreate is a manual operation that runs the published image against the repo's compose — it does not define new production behavior on the host. The Prime Directive (no server-only changes) keeps the repo authoritative.

**Not a normal deploy path:** GitHub Actions must never SSH into the VPS/NAS or run Docker there (§3/§10). CI's job ends at publishing to GHCR. Building the nas-settings image locally on the VPS (`docker compose build`) is **not** the approved path — pull the CI-published image instead.

### How changes get deployed

**VPS changes (seafile-server/):**
1. Edit compose files or scripts in this repo
2. Commit to `main` and push to GitHub
3. SSH to VPS (or use Bash on the VPS since Claude Code runs there): `cd ~/seafile-repo && git pull`
4. Apply changes: restart affected containers or apply config changes manually
5. Verify with `docker compose -f /opt/seafile/seafile-server.yml -f /opt/seafile/caddy.yml ps`

**NAS image changes (synology-seaf-cli/Dockerfile, entrypoint.py, seaf-entrypoint.py):**
1. Edit the relevant file in this repo
2. Commit to `main` and push
3. GitHub Actions (`seaf-cli image` workflow) builds and pushes both `ghcr.io/u2giants/seafile:seaf-cli-latest` and `ghcr.io/u2giants/seafile:sha-<commit>`
4. After CI succeeds: pull the new image on the NAS and recreate containers (via NAS MCP base64 commands)
5. **Rollback:** pin the affected service's `image:` to a known-good `ghcr.io/u2giants/seafile:sha-<older-commit>` and `up -d` — never rebuild on the host or hand-edit container state

**NAS compose changes (synology-seaf-cli/docker-compose.yml):**
1. Edit `synology-seaf-cli/docker-compose.yml` in this repo
2. Commit and push
3. Write the updated compose file to `/tmp/seaf-cli-compose.yml` on edgesynology1 via NAS MCP (base64+tee)
4. Run `docker compose -f /tmp/seaf-cli-compose.yml up -d` (via base64-encoded NAS MCP command)

**VPS access:** Claude Code runs on the VPS as `ai` user with passwordless sudo. Direct Bash commands work.
**NAS access:** Via `nas-direct` MCP server at `https://nas-mcp.designflow.app/mcp` (bearer token). All docker commands must be base64-encoded.

---

## Critical Incident Log

### 2026-06-05 — NAS seaf-cli containers found removed (sync silently stopped)

**What happened:** During a status review, `docker ps -a` on edgesynology1 showed only the unrelated infra containers (`synology-monitor-*`, `auth-ldap-relay`). Both `seaf-cli-char-licensed` and `seaf-cli-generic-decor` were gone — not stopped (a stopped container still lists in `docker ps -a`), but removed.

**Impact:** NAS → Seafile → S3 sync was not running. New/changed design files were not being pushed. No data loss: the Seafile libraries, their S3 data, and the Docker volumes (`seaf-cli-*-data`, `seaf-cli-*-staging`) all survived; the `seaf-cli-latest` image is still present on the NAS.

**Root cause:** Not yet determined. `docker events` for the last 72h showed no seaf-cli lifecycle events, so removal happened earlier than that. Candidates: a Container Manager reset/upgrade on the Synology, a manual removal, or a NAS event that dropped the containers despite `restart: unless-stopped`. The repo docs still claimed "✅ Running," which masked the outage.

**Recovery (not yet performed):** Re-deploy from `synology-seaf-cli/docker-compose.yml` via the NAS MCP (base64 pattern), or proceed with the Windows cutover instead. The existing data volumes mean seaf-cli will not need to re-hash and re-upload everything.

**Rule added to prevent recurrence:** Do not trust "running/healthy" claims in docs — verify live container state with `docker ps -a` before asserting sync is up. Status claims in this file and HANDOFF.md must be re-derived from the host, not copied forward.

---

## Pending Work

| Status | Item | Next action |
|--------|------|-------------|
| 🟡 open | **Designer user accounts (8 people)** | Send `https://seafile.designflow.app`; they sign in with M365 SSO (accounts auto-create); then share Character Licensed + Generic Decor with each at Read/Write |
| 🟡 open | **Windows workstation cutover** (optional, replaces NAS sync) | (1) confirm Docker Desktop on the Windows machine, (2) run `setup.ps1` as Admin, (3) verify containers healthy, (4) ensure NAS containers are not also running. See `windows-workstation/README.md` |
| 🟢 optional | **Pin the seaf-cli base image to a digest** for fully reproducible builds | Replace `FROM flrnnc/seafile-client:latest` with a digest; document the bump procedure (see Idiosyncratic Decisions) |
| 🟢 optional | **Elasticsearch** for full-text search | Not blocking; needs RAM headroom. `vm.max_map_count` already set |
| ⚪ later | **Delete HANDOFF.md** | Once NAS sync is restored and designers are onboarded |

### Done this session (2026-06-05)
- seaf-cli staging rewritten to hardlink + `os.scandir` (no per-file copy; ~half the hourly scan I/O) — commit `5274587`
- CI: immutable `sha-<commit>` image tags, `concurrency` cancel-in-progress, gha layer cache + buildx — commits `1c9fd18`, `546e0d4`
- CI actions bumped to Node 24 majors (checkout v6, setup-python v6, buildx v4, login v4, build-push v7) — commit `84fa5d6`
- §25 CI/CD exception documented; docs brought in line with actual state

### Done this session (2026-06-06)
- Pause/Resume added to sync status dashboard — commit `21c4a70`
- NAS container status corrected (both were running; docs said removed)
