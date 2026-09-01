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

The seaf-cli container runs on the Synology NAS (`edgesynology1`), bind-mounting the source folders directly. Only one host may run seaf-cli for a library at a time — two clients syncing the same library concurrently corrupts sync state.

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

Flask app that gives the Seafile web UI a GUI for the seaf-cli client at `/nas-settings/`: a live status Dashboard plus Controls (pause/resume/restart/stop), Config (any `seaf-cli config` key), Libraries (list/list-remote/create/desync plus cached NAS folder sizes), and ingest-window/sync-schedule Settings. The schedule model has separate weekday and weekend windows per library, with a shared timezone and overnight-window support. Auth delegates to Seafile: the app reads the browser's `seahub_auth` cookie and calls Seafile's admin API with token auth to verify the user is a system admin — no separate credentials. Persists state to a named Docker volume (`nas-settings-data`). Managed by `nas-settings.yml`, deployed separately from the main stack (not in `COMPOSE_FILE`).

**Control loop (server → NAS).** The VPS cannot reach the NAS, so it never pushes. The single NAS `seaf-cli` container POSTs one `/api/status` heartbeat per configured library UUID every 30 s (authenticated by `SEAF_STATUS_TOKEN`); the panel persists each report and hands back the next queued command for that UUID. If no command is queued, the response carries the current schedule for that library. The container executes commands (daemon RPC for pause/resume, otherwise `seaf-cli`) and reports the result on that library's next POST. Schedule enforcement toggles the targeted repo's `auto-sync` property. Commands are routed by **library UUID**, not the container's ephemeral Docker hostname or legacy single-library `SEAF_LIBRARY`. Destructive verbs (desync/create/reinit) require explicit confirmation.

## seaf-cli Sync Architecture

One NAS `seaf-cli` container syncs all live NAS libraries. The image is `ghcr.io/u2giants/seafile:seaf-cli-latest` — a wrapper built on `flrnnc/seafile-client` from this repo's `synology-seaf-cli/` directory.

The NAS compose file bind-mounts each source folder directly under `/library/<key>`:

```
/library/char    ← /volume1/mac/Decor/Character Licensed
/library/decor   ← /volume1/mac/Decor/Generic Decor
/library/guides  ← /volume1/styleguides
```

`entrypoint.py` discovers `SEAF_LIBRARY_<KEY>` variables, lowercases each key, and syncs that UUID to `/library/<key>`. The old `SEAF_LIBRARY` single-library mode still exists for compatibility, but if it is set the multi-library variables are intentionally ignored.

Startup flow:

```
/library/<key> (NAS bind mount, read-write)
    │
    ▼ entrypoint.py
    │  – starts seaf-daemon in /seafile
    │  – writes/refreshes seafile-ignore.txt in each target before clone-skip checks
    │  – registers each /library/<key> path with seaf-cli
    │  – before retrying an unsynced repo, clears only failed clone.db tasks for that repo
    │  – reports live status and can enforce sync schedules / scan cached folder sizes
    │
    ▼ Seafile → S3
```

`entrypoint.py` receives the current sync schedule on the 30-second status heartbeat, evaluates weekday and weekend windows in the configured timezone, toggles each repo's `auto-sync` property, and can build a cached recursive folder-size table nightly after 2 AM New York time or on command. `seafile-ignore.txt` suppresses Synology metadata and common temp files in synced library paths. It is hygiene only: Synology can regenerate local `@eaDir` trees and ignored directories may still consume inotify watches, so host inotify limits must still be sized correctly.

### Process Supervision

The wrapper image uses `tini` as PID 1, which reaps zombie processes and correctly forwards signals. The process hierarchy inside each container is:

```
tini (PID 1)
  └── python3 /home/seafile/entrypoint.py
        ├── status reporter thread (optional, every 30 s)
        ├── folder-size scheduler thread
        └── seaf-daemon
```

**Why this matters:** Prior to this wrapper image, the upstream `flrnnc/seafile-client` had three confirmed bugs that caused silent failures in production:

1. **Zombie seaf-daemon** — `seaf-cli start` made seaf-daemon a direct child of `entrypoint.py`. When seaf-daemon exited, `entrypoint.py` never called `waitpid()` (it was parked in `tail -f`), leaving a zombie process. The container stayed healthy from Docker's perspective. `tini` now reaps any zombies that get reparented to PID 1.

2. **No restart on daemon death** — `entrypoint.py` used `follow()` which ran `tail -f logfile`. When seaf-daemon died, sync stopped silently. The fixed `entrypoint.py` uses a `watch()` loop that polls `seaf-daemon`'s PID every 10 seconds and calls `sys.exit(1)` when it dies, triggering Docker's `restart: unless-stopped` policy.

3. **Healthcheck always reported healthy** — `healthcheck()` returned `None` (missing `return` statement), which `sys.exit(None)` treats as exit code 0. The fixed version returns `0 if healthy else 1`.

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

`/data/settings.json` stores each library's `ingest_days` value and schedule. Current
schedules are normalized to:

```json
{
  "enabled": true,
  "timezone": "America/New_York",
  "windows": {
    "weekdays": {"enabled": true, "days": [0, 1, 2, 3, 4], "start": "19:00", "end": "07:00"},
    "weekends": {"enabled": false, "days": [5, 6], "start": "09:00", "end": "17:00"}
  }
}
```

Day numbers follow Python's `weekday()` convention: Monday is `0`, Sunday is `6`.
The NAS agent still accepts the older one-window `{days,start,end}` shape for
backward compatibility, but the panel writes the `windows` shape.

## Networking

**Why Cloudflare proxy is disabled:** `seafile.designflow.app` is DNS-only (grey cloud). Seafile's desktop sync client uses a binary protocol on port 8082 that does not work through Cloudflare's HTTP proxy layer. Enabling the orange cloud would break all desktop sync clients. The DNS-only A record must never be changed to proxied.

**Port 8082 is not exposed externally.** It is used internally between seafile-server and seahub, both inside the same container. External file sync traffic from seaf-cli uses the standard HTTPS port 443 via the Seafile HTTP sync protocol.

## Authentication

Two methods work simultaneously:

**Microsoft 365 SSO (primary — for all staff):**
```
Login page → "Sign in with Microsoft" button → Microsoft login →
callback to /oauth/callback/ → Seafile maps by email → session
```
Tenant-locked to POP Creations (tenant ID `1caeb1c0-a087-4cb9-b046-a5e22404f971`). Only users in this M365 tenant can authenticate. Self-registration is disabled (`ENABLE_SIGNUP = False`). Azure AD app: "Seafile POP Creations" (client ID `8d9da03c-e5cd-4a23-b987-32aaaed31fe7`).

**Local password (admin fallback only):**
```
Login page → email + password form → seahub_db lookup → session
```
The current admin is the SSO-created internal user `4cba3f5721f7436fbe06a2b154ee296a@auth.local` with contact email `albert@popcre.com`. `nas-sync@popcre.com` is local-only (machine account, no SSO).

## Elasticsearch (not deployed)

`seafevents.conf` has `[INDEX FILES] enabled = true` pointing to `es_host = elasticsearch`. No Elasticsearch container exists. This causes seafevents to log connection errors every 10 minutes but is otherwise harmless — it retries silently. Full-text search inside file contents does not work; filename search does.

This is intentional: Elasticsearch requires ~2GB RAM on a 4GB server, leaving inadequate headroom for the rest of the stack. The `vm.max_map_count=262144` sysctl is already set in `/etc/sysctl.conf` if Elasticsearch is added later.
