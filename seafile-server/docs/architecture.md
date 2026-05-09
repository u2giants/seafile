# Architecture

## System Overview

```
NYC Office                          Linode VPS (172.233.14.233)              São Paulo
                                                                              
Synology NAS ──── seaf-cli ────►  seafile.designflow.app  ◄──── HTTPS ────  designers
(source of truth)  (Docker)         (Seafile Pro 13.0)         (browser/
  /volume1/mac/                            │                     desktop app)
  Decor/…                                  │ reads/writes
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
Image: `nas-settings:local` (built locally from `seafile-server/nas-settings/`)

Flask app that exposes a settings UI for the NAS sync ingest window at `/nas-settings/`. Auth delegates to Seafile: the app calls Seafile's internal admin API on every request to verify the `sessionid` cookie belongs to a system admin — no separate credentials. Persists settings to a named Docker volume (`nas-settings-data`). Managed by `nas-settings.yml`, deployed separately from the main stack (not in `COMPOSE_FILE`).

## NAS Sync Architecture

Two seaf-cli containers run on the Synology NAS (`edgesynology1`), one per library. Each follows this flow on startup and hourly:

```
/source (NAS folder, read-only bind mount)
    │
    ▼ seaf-entrypoint.py
    │  – filters files by mtime (SEAF_INGEST_DAYS)
    │  – copies qualifying files to /library staging volume
    │  – removes stale files from /library
    ▼
/library (Docker staging volume)
    │
    ▼ /home/seafile/entrypoint.py (upstream seaf-cli)
    │  – seaf-daemon syncs /library to Seafile server
    ▼
Seafile → S3
```

`seaf-entrypoint.py` is downloaded from GitHub at each container start (not mounted from disk — a workaround for NAS MCP write restrictions). It reads per-library `ingest_days` from `https://seafile.designflow.app/nas-settings/api/settings` on startup and on each hourly refresh; if that fetch fails, it falls back to `SEAF_INGEST_DAYS` from the environment.

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
  nas-settings-data              NAS settings panel persistent state (/data/settings.json)
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
