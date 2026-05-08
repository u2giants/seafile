# Architecture

## System Overview

```
Internet
    │
    ▼
[Cloudflare DNS]
seafile.designflow.app → 172.233.14.233 (DNS-only, no proxy)
    │
    ▼
[Linode VPS — 172.233.14.233]
Ubuntu 24.04 LTS, 4GB RAM, 80GB disk
    │
    ▼
[UFW Firewall]
Open: 22/tcp (SSH), 80/tcp (HTTP→HTTPS redirect), 443/tcp (HTTPS)
    │
    ▼
[Docker network: seafile-net]
┌─────────────────────────────────────────────────────┐
│                                                     │
│  ┌──────────────┐    ┌──────────────────────────┐   │
│  │ seafile-caddy│    │       seafile            │   │
│  │ (Caddy proxy)│───►│  (Seafile Pro 13.0)      │   │
│  │ ports 80,443 │    │  port 80 (internal)      │   │
│  └──────────────┘    └──────────────────────────┘   │
│                               │                     │
│                    ┌──────────┴──────────┐          │
│                    ▼                     ▼          │
│             ┌────────────┐      ┌──────────────┐   │
│             │seafile-mysql│     │ seafile-redis │   │
│             │ (MariaDB   │      │  (Redis cache)│   │
│             │  10.11)    │      │  port 6379    │   │
│             │ port 3306  │      └──────────────┘   │
│             └────────────┘                         │
└─────────────────────────────────────────────────────┘
```

## Containers

### seafile-caddy
- **Image:** `lucaslorentz/caddy-docker-proxy:2.12-alpine`
- **Role:** Reverse proxy + automatic TLS. Reads Docker labels from the `seafile` container to know where to route traffic. Handles Let's Encrypt certificate issuance and renewal automatically.
- **Ports:** 80 (HTTP, redirects to HTTPS), 443 (HTTPS)
- **Data:** TLS certificates stored at `/opt/seafile-caddy/` (persisted on host)
- **How TLS works:** Caddy reads the label `caddy: https://seafile.designflow.app` on the seafile container, automatically requests a Let's Encrypt cert for that domain, and terminates TLS. No manual cert management needed.

### seafile
- **Image:** `seafileltd/seafile-pro-mc:13.0-latest` (Docker Hub)
- **Role:** Main Seafile application. Runs both the seafile-server (file sync daemon) and seahub (Django web UI) inside a single container.
- **Internal port:** 80 (HTTP, only accessible inside Docker network — Caddy handles external TLS)
- **Data:** All persistent data mounted at `/opt/seafile-data/` (mapped to `/shared` inside container)
- **Note on image:** The deployment doc referenced `docker.seadrive.org/seafileltd/seafile-pro-mc:13.0-latest` but that tag does NOT exist on the Seafile private registry. The 13.0 Pro image is on Docker Hub as `seafileltd/seafile-pro-mc:13.0-latest`. The `latest` tag does exist on `docker.seadrive.org`.

### seafile-mysql
- **Image:** `mariadb:10.11`
- **Role:** Database for Seafile metadata — user accounts, sharing permissions, library metadata, audit logs. File data itself is NOT in the database; it's in the filesystem.
- **Databases:** `ccnet_db`, `seafile_db`, `seahub_db`
- **Data:** Persisted at `/opt/seafile-mysql/db/`

### seafile-redis
- **Image:** `redis:latest`
- **Role:** Cache for Seahub (the web UI). Speeds up session handling and frequently accessed data.
- **No persistence** configured (acceptable — it's a cache).

## Data Directory Layout

```
/opt/
├── seafile/                    ← Docker compose files and scripts (this repo)
│   ├── .env                    ← All environment variables and secrets
│   ├── seafile-server.yml      ← Main compose file (db, redis, seafile)
│   ├── caddy.yml               ← Caddy reverse proxy compose file
│   ├── CREDENTIALS.txt         ← All passwords (chmod 600, root only)
│   ├── docs/                   ← This documentation
│   ├── START_SEAFILE.sh        ← Pre-flight startup script
│   ├── CONFIGURE_OAUTH.sh      ← Google OAuth setup helper
│   └── CREATE_NAS_SYNC_ACCOUNT.sh ← NAS service account + library setup
│
├── seafile-data/               ← All Seafile application data (mounted as /shared)
│   ├── seafile-license.txt     ← Pro license file (REQUIRED)
│   └── seafile/
│       ├── conf/               ← Seafile configuration files
│       │   ├── seahub_settings.py   ← Main Seahub config (OAuth goes here)
│       │   ├── seafile.conf         ← File server config
│       │   ├── seafevents.conf      ← Background events (search, audit, stats)
│       │   ├── seafdav.conf         ← WebDAV config (disabled)
│       │   └── gunicorn.conf.py     ← Seahub WSGI server config
│       ├── logs/               ← Application logs
│       ├── seafile-data/       ← Actual file blocks (the 28TB will live here)
│       ├── seahub-data/        ← User avatars, thumbnails, etc.
│       └── pro-data/           ← Pro features data
│
├── seafile-mysql/
│   └── db/                     ← MariaDB data files
│
├── seafile-caddy/
│   ├── certificates/           ← Let's Encrypt TLS certificates
│   └── acme/                   ← ACME challenge data
│
└── backups/                    ← Daily MySQL database dumps
    └── seafile-db-YYYYMMDD.sql
```

## Networking

- All containers are on the Docker bridge network `seafile-net`.
- Only Caddy exposes ports to the host (80 and 443).
- The seafile container is NOT directly accessible from outside — all traffic goes through Caddy.
- Cloudflare DNS is set to **DNS-only (no proxy)** because Seafile's sync protocol (using the seaf-cli client) is not HTTP and breaks when routed through Cloudflare's proxy layer.

## Seafile Internals

Seafile stores files in a content-addressable format similar to Git:
- **Blocks:** File data is split into variable-size chunks (blocks), stored by content hash.
- **Commits:** Snapshots of library state, stored as commit objects.
- **File system trees (fs):** Directory tree metadata.

This is why there are three logical storage areas (blocks, commits, fs) which matter if/when S3 backend is configured — they can map to separate buckets.

## Authentication Flow (current — password only)

```
Browser → https://seafile.designflow.app → Caddy → seafile container → Seahub login page
User enters email + password → Seahub authenticates against seahub_db → Session cookie
```

## Authentication Flow (future — Google OAuth SSO)

```
Browser → Login page → "Sign in with Google" button
→ Google OAuth consent → callback to https://seafile.designflow.app/oauth/callback/
→ Seafile creates/maps user account by email → Session cookie
```
