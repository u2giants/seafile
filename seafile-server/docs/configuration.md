# Configuration Reference

## /opt/seafile/.env

Master environment file — read by Docker Compose at startup. Changing a value requires recreating the affected container (`docker compose up -d --force-recreate seafile`), except for init-only vars which are ignored after first start.

### Compose

```
COMPOSE_FILE='seafile-server.yml,caddy.yml'
```
Defines which files `docker compose` loads by default. Does not include `elasticsearch.yml` or `seadoc.yml` — those components are not deployed.

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
INIT_SEAFILE_ADMIN_EMAIL=u2giants@gmail.com
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

---

## /opt/seafile-data/seafile/conf/seahub_settings.py

Main Django settings for the Seahub web UI. Lives inside the Docker volume — persists across container restarts. After editing, run `docker restart seafile`.

**Current live content:**

```python
SECRET_KEY = "2aqy%o)8kxoix_0#jdz4uzi+r&cx+ix&8z#+w&uh^!y*(lhyp7"
TIME_ZONE = 'America/Sao_Paulo'

ENABLE_OAUTH = True
OAUTH_ENABLE_INSECURE_TRANSPORT = False
OAUTH_CLIENT_ID = '<see CREDENTIALS.txt on VPS>'
OAUTH_CLIENT_SECRET = '<see CREDENTIALS.txt on VPS>'
OAUTH_REDIRECT_URL = 'https://seafile.designflow.app/oauth/callback/'
OAUTH_PROVIDER_DOMAIN = 'accounts.google.com'
OAUTH_AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/auth'
OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'
OAUTH_USER_INFO_URL = 'https://www.googleapis.com/oauth2/v1/userinfo'
OAUTH_SCOPE = ['openid', 'email', 'profile']
OAUTH_ATTRIBUTE_MAP = {
    'id': (True, 'sub'),
    'name': (False, 'name'),
    'email': (True, 'email'),
}
```

The `CONFIGURE_OAUTH.sh` script appends this block. It is idempotent only if run once — running it twice will duplicate the block. Check the file before running.

---

## /opt/seafile-data/seafile/conf/seafile.conf

```ini
[fileserver]
port=8082
```

Minimal. Seafile generates defaults for everything else. Port 8082 is used internally within the container between seafile-server and seahub — it is not exposed to the host.

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

Seafile's private registry (`docker.seadrive.org`) — needed to pull `latest` or future versions:

```
Username: seafile
Password: zjkmid6rQibdZ=uJMuWS
```

These are Seafile's published public credentials. They may rotate — check https://customer.seafile.com/downloads/ if login fails.
