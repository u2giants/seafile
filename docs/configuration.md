# Configuration Reference

## /opt/seafile/.env

Master environment file — read by Docker Compose at startup. Changing a value requires recreating the affected container (`docker compose up -d --force-recreate seafile`), except for init-only vars which are ignored after first start.

### Compose

```
COMPOSE_FILE='seafile-server.yml,caddy.yml'
```
Defines which files `docker compose` loads by default when run from `/opt/seafile/`. **`nas-settings.yml` is not in this list** — it lives in the repo and is deployed separately (see [deployment.md](deployment.md)).

### Images

```
SEAFILE_IMAGE=seafileltd/seafile-pro-mc:13.0-latest   # Docker Hub — NOT docker.seadrive.org
SEAFILE_DB_IMAGE=mariadb:10.11
SEAFILE_REDIS_IMAGE=redis
SEAFILE_CADDY_IMAGE=lucaslorentz/caddy-docker-proxy:2.12-alpine
```

### Storage

```
SEAF_SERVER_STORAGE_TYPE=s3
S3_BLOCK_BUCKET=seafile-s3
S3_COMMIT_BUCKET=seafile-s3-commits
S3_FS_BUCKET=seafile-s3-fs
S3_KEY_ID=<Linode access key>
S3_SECRET_KEY=<Linode secret key>
S3_USE_V4_SIGNATURE=true
S3_PATH_STYLE_REQUEST=false          # Linode uses virtual-hosted style
S3_AWS_REGION=br-gru-1               # São Paulo
S3_HOST=br-gru-1.linodeobjects.com   # Override endpoint for non-AWS S3
S3_USE_HTTPS=true
S3_SSE_C_KEY=                        # Empty — no client-side encryption
```

All three buckets must be distinct — Seafile refuses to start if any two share a bucket name.

### Server identity

```
SEAFILE_SERVER_HOSTNAME=seafile.designflow.app
SEAFILE_SERVER_PROTOCOL=https        # Tells Caddy to handle TLS
TIME_ZONE=America/Sao_Paulo
JWT_PRIVATE_KEY=<64-char random>     # Signs internal service tokens
```

### Database

```
SEAFILE_MYSQL_DB_HOST=db             # Docker service name, not an IP
SEAFILE_MYSQL_DB_USER=seafile
SEAFILE_MYSQL_DB_PASSWORD=<password>
SEAFILE_MYSQL_DB_CCNET_DB_NAME=ccnet_db
SEAFILE_MYSQL_DB_SEAFILE_DB_NAME=seafile_db
SEAFILE_MYSQL_DB_SEAHUB_DB_NAME=seahub_db
```

### Cache

```
CACHE_PROVIDER=redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=                      # Empty — Redis is not exposed outside Docker network
```

### Init-only (first container start only — ignored thereafter)

```
INIT_SEAFILE_ADMIN_EMAIL=<initial admin email; init-only, not necessarily a current active user>
INIT_SEAFILE_ADMIN_PASSWORD=<password>
INIT_SEAFILE_MYSQL_ROOT_PASSWORD=<password>
```

These create the initial admin account and set the MariaDB root password. They are never re-applied once Seafile has initialised. Changing them in `.env` after first start has no effect.

### Disabled features

```
ENABLE_SEADOC=false
ENABLE_NOTIFICATION_SERVER=false
ENABLE_SEAFILE_AI=false
ENABLE_FACE_RECOGNITION=false
```

### NAS settings panel

```
NAS_SETTINGS_SECRET_KEY=<random string>    # Flask session signing key
NAS_STATUS_TOKEN=<random string>           # shared with seaf-cli containers for status POST auth
```

Used by the `nas-settings` container. `SEAFILE_INTERNAL_URL` and `SEAFILE_PUBLIC_HOST` are hardcoded in `nas-settings.yml` (not sourced from `.env`) because they are deployment-invariant for this installation.

The panel persists per-library ingest/schedule settings in the `nas-settings-data`
Docker volume at `/data/settings.json`. The schedule stored for each library has
this normalized shape:

```json
{
  "enabled": false,
  "timezone": "America/New_York",
  "windows": {
    "weekdays": {"enabled": true, "days": [0, 1, 2, 3, 4], "start": "19:00", "end": "07:00"},
    "weekends": {"enabled": false, "days": [5, 6], "start": "09:00", "end": "17:00"}
  }
}
```

`enabled` gates the whole schedule. Each window has its own enabled flag, fixed
day set, and start/end time. End earlier than start means the window runs
overnight. The NAS agent also accepts the previous one-window schedule shape for
backward compatibility, but the panel now writes weekday/weekend windows.

### NAS seaf-cli agent

These environment variables are set in `synology-seaf-cli/docker-compose.yml` or the
host env file used with it:

| Variable | Purpose |
|----------|---------|
| `SEAF_SERVER_URL` | Public Seafile URL used by `seaf-cli`. |
| `SEAF_USERNAME` / `SEAF_PASSWORD` | Local machine account credentials for `nas-sync@popcre.com`. |
| `SEAF_LIBRARY_<KEY>` | Multi-library NAS mode. The suffix becomes the `/library/<key>` subfolder and the value is the library UUID, for example `SEAF_LIBRARY_CHAR`, `SEAF_LIBRARY_DECOR`, and `SEAF_LIBRARY_GUIDES`. |
| `SEAF_LIBRARY` | Legacy/single-library mode. If set, multi-library variables are ignored. |
| `SEAF_SETTINGS_URL` | `nas-settings` `/api/settings` URL for ingest settings and non-secret schedule metadata. |
| `SEAF_STATUS_TOKEN` | Shared token used when posting status to `/api/status`. |
| `SEAF_UPLOAD_LIMIT` / `SEAF_DOWNLOAD_LIMIT` | Optional seaf-cli transfer limits in KB/s. |
| `SEAF_MIN_INOTIFY_WATCHES` | Minimum acceptable Synology host inotify watch limit before the status dashboard reports an anomaly. Default: `1048576`. |
| `SEAF_INOTIFY_WARN_USAGE` | Fraction of `max_user_watches` at which the wrapper reports high inotify usage. Default: `0.80`. |
| `SEAF_CANARY_FILENAME` | Per-library production-tree canary filename. Default: `.seafile-sync-canary.json`. |
| `SEAF_CANARY_INTERVAL_SECONDS` | Minimum time between automatic canary rewrites. Default: `600`. |
| `SEAF_CANARY_GRACE_SECONDS` | Time allowed for the server to receive a new canary before reporting an anomaly. Default: `180`. |
| `SEAF_ALERT_WEBHOOK_URL` | Optional webhook for human-visible sync anomaly alerts. Leave unset to only show red status in the dashboard. |
| `SEAF_ALERT_COOLDOWN_SECONDS` | Minimum seconds between duplicate anomaly alerts. Default: `3600`. |

---

## /opt/seafile-data/seafile/conf/seahub_settings.py

Main Django settings for the Seahub web UI. Lives inside the Docker volume — persists across container restarts. After editing, run `docker restart seafile`.

**Current live content (Microsoft 365 SSO — tenant-locked to POP Creations):**

```python
SECRET_KEY = "..."
TIME_ZONE = 'America/Sao_Paulo'

ENABLE_OAUTH = True
OAUTH_ENABLE_INSECURE_TRANSPORT = False
OAUTH_CLIENT_ID = '<see CREDENTIALS.txt on VPS>'
OAUTH_CLIENT_SECRET = '<see CREDENTIALS.txt on VPS>'
OAUTH_REDIRECT_URL = 'https://seafile.designflow.app/oauth/callback/'
OAUTH_PROVIDER_DOMAIN = 'designflow.app'
TENANT = '1caeb1c0-a087-4cb9-b046-a5e22404f971'
OAUTH_AUTHORIZATION_URL = f'https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/authorize'
OAUTH_TOKEN_URL = f'https://login.microsoftonline.com/{TENANT}/oauth2/v2.0/token'
OAUTH_USER_INFO_URL = 'https://graph.microsoft.com/oidc/userinfo'
OAUTH_SCOPE = ['openid', 'profile', 'email']
OAUTH_ATTRIBUTE_MAP = {
    'sub':   (True,  'uid'),
    'email': (False, 'contact_email'),
    'name':  (False, 'name'),
}
ENABLE_SIGNUP = False
```

The tenant-specific authorization/token URLs (with the tenant ID rather than `/common/`) mean only POP Creations M365 users can authenticate. `ENABLE_SIGNUP = False` prevents local open signup.

**Current admin identity:** the active admin is the SSO-created internal user `4cba3f5721f7436fbe06a2b154ee296a@auth.local` with contact email `albert@popcre.com`.

---

## /opt/seafile-data/seafile/conf/seafile.conf

```ini
[fileserver]
port=8082
use_go_fileserver = true
max_sync_file_count = 5000000
fs_id_list_request_timeout = 600
```

Port 8082 is used internally within the container between seafile-server and seahub — it is not exposed to the host. `max_sync_file_count = 5000000` and `fs_id_list_request_timeout = 600` were added on 2026-06-11 after the Character Licensed library exceeded Seafile's default sync file-count limit; keep them unless the library structure changes enough to prove a lower limit is safe. Live backups from that edit were written next to the file as timestamped `.bak.*` copies.

---

## /opt/seafile-data/seafile/conf/seafevents.conf

```ini
[SEAHUB EMAIL]
enabled = true
interval = 30m

[STATISTICS]
enabled = true

[AUDIT]
enabled = true

[INDEX FILES]
external_es_server = true
es_host = elasticsearch      # ← this host does not exist; intentionally not deployed
es_port = 9200
enabled = true
interval = 10m
index_office_pdf = true

[FILE HISTORY]
enabled = true
suffix = md,txt,doc,docx,xls,xlsx,ppt,pptx,sdoc
```

The `[INDEX FILES]` section failing silently is intentional — see [architecture.md](architecture.md) for reasoning. Seafevents logs a connection error every 10 minutes; this is expected and harmless.

---

## /opt/seafile-data/seafile/conf/seafdav.conf

```ini
[WEBDAV]
enabled = false
```

WebDAV is disabled. To enable: set `enabled = true` and `docker restart seafile`. No firewall changes needed — WebDAV routes through Caddy on port 443.

---

## /opt/seafile-data/seafile/seahub-data/custom/templates/

Seahub loads templates from this directory before its own `seahub/templates/`. The only override currently in place is `sysadmin/sysadmin_react_app.html`, which is a verbatim copy of Seafile's built-in template plus a MutationObserver script that injects a "NAS Sync Settings" link into the System Admin sidebar nav after the React bundle renders.

**Maintenance note:** This template duplicates Seafile's built-in file. If Seafile is upgraded and the upstream template changes, this copy must be manually diffed and updated. The source is at `/opt/seafile/seafile-pro-server-<version>/seahub/seahub/templates/sysadmin/sysadmin_react_app.html` inside the container.

---

## Cron Jobs (root crontab)

```
0 3 * * *   docker exec seafile-mysql mysqldump ... --all-databases > /opt/backups/seafile-db-YYYYMMDD.sql
0 4 * * *   find /opt/backups -name '*.sql' -mtime +30 -delete
```

Backs up all three MariaDB databases daily. Does **not** back up file data — that lives in S3 and inherits Linode's durability guarantees.

---

## System

| Setting | Value | Set in |
|---------|-------|--------|
| `vm.max_map_count` | 262144 | `/etc/sysctl.conf` |
| UFW | 22, 80, 443 open | `ufw` |
| Docker on boot | enabled | `systemctl enable docker` |
| containerd on boot | enabled | `systemctl enable containerd` |

---

## Docker Registry Credentials

This deployment currently uses Docker Hub image `seafileltd/seafile-pro-mc:13.0-latest`, not `docker.seadrive.org`, for the Seafile server.

If a future upgrade requires Seafile's private registry, obtain current registry instructions from Seafile's official customer/download portal and keep credential values out of this repo.
