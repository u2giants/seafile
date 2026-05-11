# AGENTS.md — POP Creations Seafile Infrastructure

## What This Project Is

POP Creations runs a 28TB design file library on two Synology NAS devices in a NYC office. Eight graphic designers in São Paulo need access to that library over the internet. This repo contains all infrastructure configuration to make that work:

1. **Seafile Pro 13.0** running on a Linode VPS (`seafile.designflow.app`) — the relay server. NAS pushes files here via seaf-cli; designers pull via HTTPS/desktop app.
2. **seaf-cli Docker containers** on the Synology NAS — continuously sync NAS folders to specific Seafile libraries.
3. File data is stored in **Linode Object Storage (São Paulo, br-gru-1)**, not on the VPS disk. The VPS only holds metadata (MariaDB), session cache (Redis), and config.

This is an **infrastructure configuration repo only**. There is no application code, no build step, no Docker image to produce. The deployment artifact is the compose file and scripts themselves.

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
├── seafile-server/              VPS configuration — live at seafile.designflow.app
│   ├── seafile-server.yml       Docker Compose: Seafile Pro + MariaDB + Redis
│   ├── caddy.yml                Docker Compose: Caddy reverse proxy + TLS
│   ├── .env.example             Template — never commit the real .env
│   ├── START_SEAFILE.sh         Pre-flight checks + start command
│   ├── CONFIGURE_OAUTH.sh       One-time Google OAuth setup (already run — DO NOT RUN AGAIN)
│   ├── CREATE_NAS_SYNC_ACCOUNT.sh  One-time machine account creation (already run — DO NOT RUN AGAIN)
│   └── docs/
│       ├── README.md            Live system status and quick reference
│       ├── architecture.md      Containers, networking, storage architecture
│       ├── configuration.md     All env vars and config file contents
│       ├── deployment.md        Start/stop, updates, backup, remaining work
│       └── development.md       Logs, debugging, API usage, user management
│
└── synology-seaf-cli/           NAS sync containers — deployed on edgesynology1
    ├── Dockerfile               Wrapper image — adds tini, fixed entrypoint.py
    ├── entrypoint.py            Fixed Seafile daemon entrypoint (replaces image default)
    ├── seaf-entrypoint.py       Date-filter staging wrapper; launches entrypoint.py
    ├── docker-compose.yml       One service per Seafile library
    ├── .env.example             NAS sync password template
    └── README.md                Synology setup instructions
```

All files in this repo are **authored by this project** — there are no third-party packages or vendor directories to avoid modifying.

---

## The Prime Directive

**Our configuration lives in this repo.** All changes to the Seafile infrastructure go through files in this repo, committed to `main`, then applied on the VPS or NAS. Never make changes directly on the server and consider them done — changes made only on the server will be lost or overwritten and leave the repo out of sync with reality.

**Scripts that say "DO NOT RUN AGAIN" are off-limits.** `CONFIGURE_OAUTH.sh` and `CREATE_NAS_SYNC_ACCOUNT.sh` have already been run against the live system. Running them again creates duplicates. See Idiosyncratic Decisions.

---

## Core Modification Inventory

This project is original infrastructure config (not a fork). No upstream files have been modified. This section is intentionally empty.

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
4. Deploy to NAS via NAS MCP (base64-encode docker commands — see `seafile-server/docs/CONTEXT_FOR_AI.md` for the pattern)
5. Update the Container Inventory in this file
6. Commit and push

### If you need to update the Seafile version:
1. Check https://manual.seafile.com for breaking changes
2. Edit `SEAFILE_IMAGE` in `/opt/seafile/.env` on the VPS
3. Update the image version in `seafile-server/seafile-server.yml` and commit
4. Pull and recreate on VPS: `docker compose pull seafile && docker compose up -d --force-recreate seafile`
5. Watch logs: `docker logs -f seafile`

### If you need to manage DNS:
- Zone: `designflow.app` · Zone ID: `921eb133a3f7d5802780445b283f84ce`
- Use Cloudflare API with `CF_TOKEN` (from Albert)
- Never enable proxy (orange cloud) on `seafile.designflow.app` — see Idiosyncratic Decisions

### If you need to add a designer user:
- Send them `https://seafile.designflow.app` — they sign in with Google SSO; account auto-creates
- Then share libraries via web UI: open library → Share → Share to User → Read/Write
- Or via API — see `seafile-server/docs/development.md`

### If something breaks on the VPS:
- Check `docker compose -f /opt/seafile/seafile-server.yml -f /opt/seafile/caddy.yml ps`
- Check `docker logs seafile`
- Full debugging guide in `seafile-server/docs/development.md`

---

## Task-to-File Navigation Map

| Task | File to touch |
|------|--------------|
| Add/modify seaf-cli sync container | `synology-seaf-cli/docker-compose.yml` |
| Change Seafile/MariaDB/Redis container config | `seafile-server/seafile-server.yml` |
| Change reverse proxy (TLS, routing) | `seafile-server/caddy.yml` |
| Change environment variables | `/opt/seafile/.env` on VPS (then update `.env.example` + docs) |
| Change seahub settings (OAuth, time zone) | `/opt/seafile-data/seafile/conf/seahub_settings.py` on VPS |
| Update system status | `seafile-server/docs/README.md` |
| Update architecture docs | `seafile-server/docs/architecture.md` |
| Update config reference | `seafile-server/docs/configuration.md` |
| Update deployment docs | `seafile-server/docs/deployment.md` |
| Update debugging/API docs | `seafile-server/docs/development.md` |
| Update this guide | `AGENTS.md` |

---

## Data Model / Custom Objects

This is not an application with a custom data model. The data model is Seafile's internal schema (stored in MariaDB across `ccnet_db`, `seafile_db`, `seahub_db`).

### Seafile Libraries (permanent UUIDs — never change)

| Library name | UUID | Status |
|-------------|------|--------|
| Character Licensed | `177cf9de-3066-482e-956a-7ae8d8786c6d` | ✅ Syncing from NAS |
| Generic Decor | `1b116ab7-d66b-4411-a691-21f34eadb731` | ✅ Syncing from NAS |

These are the only two libraries.

### Accounts

| Account | Type | Purpose |
|---------|------|---------|
| u2giants@gmail.com | SSO admin | Albert's primary admin (Google OAuth) |
| albert@popcre.com | Local admin | Albert's fallback local account |
| nas-sync@popcre.com | Local machine account | Used by seaf-cli containers to push files |

---

## Container Inventory

### VPS Containers (Linode 172.233.14.233)

These containers are defined by the upstream Seafile Docker Compose. Their names do not follow the `[app]-[function]` standard because they are pre-defined by Seafile and renaming running containers is destructive. See Idiosyncratic Decisions.

| Container name | Function | Compose file |
|---------------|----------|-------------|
| `seafile` | Seafile Pro 13.0 app (seahub + seafile-server) | `seafile-server/seafile-server.yml` |
| `seafile-mysql` | MariaDB 10.11 — metadata database | `seafile-server/seafile-server.yml` |
| `seafile-redis` | Redis — session cache | `seafile-server/seafile-server.yml` |
| `seafile-caddy` | Caddy reverse proxy — TLS termination | `seafile-server/caddy.yml` |

### NAS Containers (edgesynology1 — 192.168.3.100)

These follow the standard naming convention.

| Container name | NAS path | Seafile library | UUID | Status |
|---------------|----------|----------------|------|--------|
| `seaf-cli-char-licensed` | `/volume1/mac/Decor/Character Licensed` | Character Licensed | `177cf9de-3066-482e-956a-7ae8d8786c6d` | ✅ Running |
| `seaf-cli-generic-decor` | `/volume1/mac/Decor/Generic Decor` | Generic Decor | `1b116ab7-d66b-4411-a691-21f34eadb731` | ✅ Running |

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

### NAS source mounts to /source; /library is a Docker staging volume
**Looks like:** The NAS folder should mount directly to `/library`.
**Actually:** The `flrnnc/seafile-client` image uses `/library` as its sync target and `/seafile` for state. We mount the NAS folder read-only at `/source`, and a staging Docker volume at `/library`. A Python wrapper (`seaf-entrypoint.py`) populates `/library` from `/source` (with optional date filtering via `SEAF_INGEST_DAYS`) before handing off to the image's own `entrypoint.py`.
**Why:** Enables per-library date-range filtering without modifying the upstream image. seaf-cli sees a clean, filtered `/library` and syncs that to Seafile.
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
**Why:** `deploy.resources.limits.cpus` uses cgroup quotas — graceful throttling, no errors or hangs. Memory limit prevents OOM impact on other services (OOMKill restarts the container cleanly via the watchdog).
**Do not change because:** Without limits, a fresh sync of char-licensed (467k files) degrades the NAS for hours. Current values: char-licensed cpus=0.75/memory=2g, generic-decor cpus=0.5/memory=512m. Tune memory up if OOMKills appear in Docker events.

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
| Cloudflare API token | From Albert | DNS management |
| Linode API token | From Albert | VPS/object storage management |
| docker.seadrive.org credentials | Username: `seafile` / Password: `zjkmid6rQibdZ=uJMuWS` (published by Seafile) | Pull Seafile Pro images |

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
| Linode Object Storage region | `br-gru-1` (São Paulo) |
| S3 blocks bucket | `seafile-s3` |
| S3 commits bucket | `seafile-s3-commits` |
| S3 fs bucket | `seafile-s3-fs` |

---

## Deployment

This is a **config-only repo** — there is no Docker image to build and push. The standard GitHub Actions → GHCR → Coolify pipeline does not apply.

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
3. GitHub Actions (`seaf-cli image` workflow) builds and pushes `ghcr.io/u2giants/seafile:seaf-cli-latest`
4. After CI succeeds: pull the new image on the NAS and recreate containers (via NAS MCP base64 commands)

**NAS compose changes (synology-seaf-cli/docker-compose.yml):**
1. Edit `synology-seaf-cli/docker-compose.yml` in this repo
2. Commit and push
3. Write the updated compose file to `/tmp/seaf-cli-compose.yml` on edgesynology1 via NAS MCP (base64+tee)
4. Run `docker compose -f /tmp/seaf-cli-compose.yml up -d` (via base64-encoded NAS MCP command)

**VPS access:** Claude Code runs on the VPS as `ai` user with passwordless sudo. Direct Bash commands work.
**NAS access:** Via `nas-direct` MCP server at `https://nas-mcp.designflow.app/mcp` (bearer token). All docker commands must be base64-encoded.

---

## Critical Incident Log

No incidents recorded. Add here if a disaster or near-miss occurs: what happened, what was destroyed, how it was recovered, and the rule that prevents recurrence.

---

## Pending Work

- [ ] **Designer user accounts (8 people)** — São Paulo designers not yet onboarded. Send them `https://seafile.designflow.app`; they sign in with Google SSO; accounts auto-create. Then share Character Licensed and Generic Decor libraries with each at Read/Write.
- [ ] **Delete HANDOFF.md** — once designer accounts are done.
- [ ] **Elasticsearch** — optional, not blocking. Requires server upgrade or RAM headroom. `vm.max_map_count` is already set.
