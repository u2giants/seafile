# Architecture

## System Overview

```
NYC Office                          Linode VPS (172.233.14.233)              São Paulo
                                                                              
Synology NAS ──── seaf-cli ────►  seafile.designflow.app  ◄──── HTTPS ────  8 designers
(source of truth)  (Docker)         (Seafile Pro 13.0)         (browser/
  28TB library                             │                     desktop app)
                                           │ reads/writes
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

All four containers run on a single bridge network (`seafile-net`). Only Caddy exposes ports to the host.

```
Host ports 80, 443
      │
      ▼
┌─────────────────────────────────────────────────┐
│ Docker network: seafile-net                     │
│                                                 │
│  seafile-caddy ──────────► seafile              │
│  (Caddy proxy)              (Seafile Pro app)   │
│  ports 80, 443              port 80 internal    │
│                                    │            │
│                          ┌─────────┴────────┐  │
│                          ▼                  ▼  │
│                    seafile-mysql       seafile-redis
│                    (MariaDB 10.11)     (Redis cache)
│                    port 3306           port 6379    
└─────────────────────────────────────────────────┘
```

### seafile-caddy
Image: `lucaslorentz/caddy-docker-proxy:2.12-alpine`

Reads Docker labels off the `seafile` container (`caddy: https://seafile.designflow.app`) to configure routing automatically. Handles Let's Encrypt issuance and renewal — no manual cert management. TLS state persisted at `/opt/seafile-caddy/`.

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

## Storage Architecture

Seafile uses a content-addressable format (similar to Git) split across three logical stores:

| Store | Contains | S3 Bucket |
|-------|----------|-----------|
| blocks | File data, chunked by content hash | `seafile-s3` |
| commits | Library snapshots (version history) | `seafile-s3-commits` |
| fs | Directory tree metadata | `seafile-s3-fs` |

Seafile requires these to be **separate buckets** — it will refuse to start if two stores share a bucket. All three buckets are in Linode Object Storage `br-gru-1` (São Paulo), which minimises latency for Brazilian designers reading files.

**Why separate buckets matter for recovery:** Each bucket type has a different access pattern and could theoretically be restored independently. Blocks contain actual file data; commits contain version history; fs contains current directory state.

## Directory Layout on VPS

```
/opt/
├── seafile/                     Compose files, scripts, secrets
│   ├── .env                     All runtime config and credentials
│   ├── seafile-server.yml
│   ├── caddy.yml
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
│       ├── seahub-data/         Avatars, thumbnails, static overrides
│       └── pro-data/            Pro feature state
│
├── seafile-mysql/db/            MariaDB data files
├── seafile-caddy/               Caddy TLS certificates and ACME state
└── backups/                     Daily SQL dumps (seafile-db-YYYYMMDD.sql)
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
`albert@popcre.com` has a local password in CREDENTIALS.txt. Use this if SSO is unavailable. `nas-sync@popcre.com` is local-only (machine account). `u2giants@gmail.com` also has a local password (the initial admin password set during first start — see CREDENTIALS.txt).

Authentication is M365 SSO (tenant-locked to POP Creations). `albert@popcre.com` and `u2giants@gmail.com` also have local passwords in CREDENTIALS.txt as a fallback.

## Elasticsearch (not deployed)

`seafevents.conf` has `[INDEX FILES] enabled = true` pointing to `es_host = elasticsearch`. No Elasticsearch container exists. This causes seafevents to log connection errors every 10 minutes but is otherwise harmless — it retries silently. Full-text search inside file contents does not work; filename search does.

This is intentional: Elasticsearch requires ~2GB RAM on a 4GB server, leaving inadequate headroom for the rest of the stack. The `vm.max_map_count=262144` sysctl is already set in `/etc/sysctl.conf` if Elasticsearch is added later.
