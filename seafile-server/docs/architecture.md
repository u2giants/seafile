# Architecture

## System Overview

```
NYC Office                          Linode VPS (172.233.14.233)              São Paulo
                                                                              
Synology NAS ─── seaf-cli ──────►  seafile.designflow.app  ◄──── HTTPS ────  designers
(source of truth)  (Docker, on       (Seafile Pro 13.0)          (browser/
  /volume1/mac/    NAS directly or           │                    desktop app)
  Decor/…          via SMB from LAN)         │ reads/writes
                                             ▼
                                    Linode Object Storage
                                      br-gru-1 (São Paulo)
                                    ┌──────────────────────┐
                                    │ seafile-s3  (blocks) │
                                    │ seafile-s3-commits   │
                                    │ seafile-s3-fs        │
                                    └──────────────────────┘
```

The VPS does not store file data on disk. All file blocks go to S3. The VPS disk holds only the database (MariaDB), Caddy TLS state, and application config.

The seaf-cli containers can run on the Synology NAS (bind-mounting source folders directly) or on a Windows workstation on the same LAN (mounting the same folders over CIFS/SMB). Only one deployment should be active at a time — running both simultaneously causes two clients to sync the same library concurrently.

## Docker Stack

Five containers run on a single bridge network (`seafile-net`). Only Caddy exposes ports to the host.

```
Host ports 80, 443
      │
      ▼
┌──────────────────────────────────────────────────────┐
│ Docker network: seafile-net                          │
│                                                      │
│  seafile-caddy ──────────► seafile                   │
│  (Caddy proxy)              (Seafile Pro app)        │
│  ports 80, 443              port 80 internal         │
│      │                            │                  │
│      │                  ┌─────────┴────────┐         │
│      │                  ▼                  ▼         │
│      │            seafile-mysql       seafile-redis   │
│      │            (MariaDB 10.11)     (Redis cache)  │
│      │            port 3306           port 6379      │
│      │                                               │
│      └──────────► nas-settings                       │
│                   (Flask, /nas-settings/*)            │
│                   port 5000 internal                 │
└──────────────────────────────────────────────────────┘
```

### seafile-caddy
Image: `lucaslorentz/caddy-docker-proxy:2.12-alpine`

Reads Docker labels off sibling containers to configure routing automatically. Routes the root domain to `seafile` and `/nas-settings/*` to `nas-settings`. Handles Let's Encrypt issuance and renewal — no manual cert management. TLS state persisted at `/opt/seafile-caddy/`.

### seafile
Image: `seafileltd/seafile-pro-mc:13.0-latest` (Docker Hub)

**Image note:** Seafile's own registry (`docker.seadrive.org`) does not have a `13.0-latest` tag — only a floating `latest`. The versioned 13.0 image is on Docker Hub. This is not obvious from Seafile's documentation.

Runs seafile-server (file sync daemon) and seahub (Django web UI) in a single container. All persistent application data is mounted at `/opt/seafile-data/` (→ `/shared` inside the container). File data is written to S3, not to this volume.

### seafile-mysql
Image: `mariadb:10.11`

Stores Seafile metadata only: user accounts, library metadata, sharing permissions, audit logs, version history references. Three databases: `ccnet_db`, `seafile_db`, `seahub_db`. Persisted at `/opt/seafile-mysql/db/`.

### seafile-redis
Image: `redis:latest`

Seahub session cache. No persistence configured — acceptable for a cache. Restarts empty; sessions are re-established from the database.

### nas-settings
Image: `ghcr.io/u2giants/seafile:nas-settings-latest` (CI-built + published from `seafile-server/nas-settings/`)

Flask app that gives the Seafile web UI a GUI for the seaf-cli client at `/nas-settings/`: a live status Dashboard plus Controls (pause/resume/restart/stop), Config (any `seaf-cli config` key), Libraries (list/list-remote/create/desync), and the ingest-window Settings. Auth delegates to Seafile: the app calls Seafile's internal admin API on every request to verify the `sessionid` cookie belongs to a system admin — no separate credentials. Persists state to a named Docker volume (`nas-settings-data`). Managed by `nas-settings.yml`, deployed separately from the main stack (not in `COMPOSE_FILE`).

**Control loop (server → NAS).** The VPS cannot reach the NAS, so it never pushes. Each seaf-cli container's status reporter POSTs to `/api/status` every 30 s (authenticated by `SEAF_STATUS_TOKEN`); the panel persists the report and hands back the next queued command in the response. The container executes it (daemon RPC for pause/resume, otherwise `seaf-cli`) and reports the result on its next POST. Commands are routed by **library UUID**, not the container's ephemeral hostname. Destructive verbs (desync/create/reinit) require explicit confirmation.

## seaf-cli Sync Architecture

Two seaf-cli containers run one per library. The image is `ghcr.io/u2giants/seafile:seaf-cli-latest` — a wrapper built on `flrnnc/seafile-client` from this repo's `synology-seaf-cli/` directory.

Each container follows this flow on startup and hourly:

```
/source (source files, read-only)
    │  On NAS:      bind mount from /volume1/mac/Decor/…
    │  On Windows:  CIFS named volume from //edgesynology1/mac/Decor/… over LAN
    │
    ▼ seaf-entrypoint.py
    │  – selects files by mtime (SEAF_INGEST_DAYS) in one os.scandir pass
    │  – hardlinks qualifying files into /library staging volume
    │    (copy2 fallback only if /source and /library are on different filesystems)
    │  – removes stale files from /library
    │  – starts hourly refresh thread (kept alive by subprocess.run below)
    ▼
/library (Docker named volume — staging)
    │
    ▼ entrypoint.py (fixed version, baked into wrapper image)
    │  – starts seaf-daemon
    │  – syncs /library to Seafile server via seaf-cli
    │  – watchdog loop: exits code 1 if seaf-daemon dies
    ▼
Seafile → S3
```

`seaf-entrypoint.py` reads per-library `ingest_days` from `https://seafile.designflow.app/nas-settings/api/settings` on startup and on each hourly refresh; falls back to `SEAF_INGEST_DAYS` from the environment if the fetch fails.

### Deployment options

| | NAS (`synology-seaf-cli/`) | Windows workstation (`windows-workstation/`) |
|---|---|---|
| Source mount | Local bind mount | CIFS named volume over LAN SMB |
| CPU load | Runs on the NAS | Offloaded to Windows machine |
| Setup | NAS MCP base64 commands | `setup.ps1` run once as Administrator |
| seaf-entrypoint.py | Identical | Identical |
| Docker image | Identical | Identical |

Only one deployment should be active at a time. To cut over: start the new deployment, verify both containers healthy, then stop the old deployment.

### Process Supervision

The wrapper image uses `tini` as PID 1, which reaps zombie processes and correctly forwards signals. The process hierarchy inside each container is:

```
tini (PID 1)
  └── seaf-entrypoint.py
        ├── refresh_loop thread (hourly re-populate /library)
        └── entrypoint.py [subprocess]
              └── seaf-daemon
```

**Why this matters:** Prior to this wrapper image, the upstream `flrnnc/seafile-client` had three confirmed bugs that caused silent failures in production:

1. **Zombie seaf-daemon** — `seaf-cli start` made seaf-daemon a direct child of `entrypoint.py`. When seaf-daemon exited, `entrypoint.py` never called `waitpid()` (it was parked in `tail -f`), leaving a zombie process. The container stayed healthy from Docker's perspective. `tini` now reaps any zombies that get reparented to PID 1.

2. **No restart on daemon death** — `entrypoint.py` used `follow()` which ran `tail -f logfile`. When seaf-daemon died, sync stopped silently. The fixed `entrypoint.py` uses a `watch()` loop that polls `seaf-daemon`'s PID every 10 seconds and calls `sys.exit(1)` when it dies, triggering Docker's `restart: unless-stopped` policy.

3. **Healthcheck always reported healthy** — `healthcheck()` returned `None` (missing `return` statement), which `sys.exit(None)` treats as exit code 0. The fixed version returns `0 if healthy else 1`.

**Why `seaf-entrypoint.py` uses `subprocess.run` instead of `os.execv`:** The original design used `os.execv` to hand off to `entrypoint.py`, which replaces the process image and kills all threads — including the hourly `refresh_loop` thread. With `os.execv`, the ingest window never slid forward between restarts. Using `subprocess.run` keeps `seaf-entrypoint.py` alive as the parent, so the refresh thread runs every hour as intended.

## Storage Architecture

Seafile uses a content-addressable format (similar to Git) split across three logical stores:

| Store | Contains | S3 Bucket |
|-------|----------|-----------|
| blocks | File data, chunked by content hash | `seafile-s3` |
| commits | Library snapshots (version history) | `seafile-s3-commits` |
| fs | Directory tree metadata | `seafile-s3-fs` |

Seafile requires these to be **separate buckets** — it will refuse to start if two stores share a bucket. All three buckets are in Linode Object Storage `br-gru-1` (São Paulo), which minimises latency for Brazilian designers reading files.

## Directory Layout on VPS

```
/opt/
├── seafile/                     Compose files, scripts, secrets
│   ├── .env                     All runtime config and credentials
│   ├── seafile-server.yml       Core stack (seafile, db, redis)
│   ├── caddy.yml                Caddy reverse proxy
│   └── CREDENTIALS.txt          All passwords, UUIDs (chmod 600, root only)
│
├── seafile-data/                Mounted as /shared in seafile container
│   ├── seafile-license.txt      Pro license (required at startup)
│   └── seafile/
│       ├── conf/                Config files (edited in place, persist across restarts)
│       │   ├── seahub_settings.py
│       │   ├── seafile.conf
│       │   ├── seafevents.conf
│       │   ├── seafdav.conf
│       │   └── gunicorn.conf.py
│       ├── logs/
│       ├── seafile-data/        Empty — file blocks go to S3, not here
│       ├── seahub-data/
│       │   └── custom/
│       │       └── templates/   Django template overrides (sysadmin nav injection)
│       └── pro-data/            Pro feature state
│
├── seafile-mysql/db/            MariaDB data files
├── seafile-caddy/               Caddy TLS certificates and ACME state
└── backups/                     Daily SQL dumps (seafile-db-YYYYMMDD.sql)

Docker volumes:
  nas-settings-data              NAS panel state (/data/settings.json, status.json, commands.json, results.json)
```

## Networking

**Why Cloudflare proxy is disabled:** `seafile.designflow.app` is DNS-only (grey cloud). Seafile's desktop sync client uses a binary protocol on port 8082 that does not work through Cloudflare's HTTP proxy layer. Enabling the orange cloud would break all desktop sync clients. The DNS-only A record must never be changed to proxied.

**Port 8082 is not exposed externally.** It is used internally between seafile-server and seahub, both inside the same container. External file sync traffic from seaf-cli uses the standard HTTPS port 443 via the Seafile HTTP sync protocol.

## Authentication

Two methods work simultaneously:

**Microsoft 365 SSO (primary — for all staff):**
```
Login page → "Single Sign-On" button → Microsoft login →
callback to /oauth/callback/ → Seafile maps by email → session
```
Tenant-locked to POP Creations (tenant ID `1caeb1c0-a087-4cb9-b046-a5e22404f971`). Only users in this M365 tenant can authenticate. Self-registration is disabled (`ENABLE_SIGNUP = False`). Azure AD app: "Seafile POP Creations" (client ID `8d9da03c-e5cd-4a23-b987-32aaaed31fe7`).

**Local password (admin fallback only):**
```
Login page → email + password form → seahub_db lookup → session
```
`albert@popcre.com` and `u2giants@gmail.com` have local passwords in CREDENTIALS.txt. Use these if SSO is unavailable. `nas-sync@popcre.com` is local-only (machine account, no SSO).

## Elasticsearch (not deployed)

`seafevents.conf` has `[INDEX FILES] enabled = true` pointing to `es_host = elasticsearch`. No Elasticsearch container exists. This causes seafevents to log connection errors every 10 minutes but is otherwise harmless — it retries silently. Full-text search inside file contents does not work; filename search does.

This is intentional: Elasticsearch requires ~2GB RAM on a 4GB server, leaving inadequate headroom for the rest of the stack. The `vm.max_map_count=262144` sysctl is already set in `/etc/sysctl.conf` if Elasticsearch is added later.
