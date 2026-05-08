# Configuration Reference

## /opt/seafile/.env

The master environment file read by Docker Compose at startup. All secrets and runtime parameters live here.

```
COMPOSE_FILE='seafile-server.yml,caddy.yml'   # Which compose files to load by default
```

### Image versions
```
SEAFILE_IMAGE=seafileltd/seafile-pro-mc:13.0-latest   # From Docker Hub (NOT docker.seadrive.org for 13.0)
SEAFILE_DB_IMAGE=mariadb:10.11
SEAFILE_REDIS_IMAGE=redis
SEAFILE_CADDY_IMAGE=lucaslorentz/caddy-docker-proxy:2.12-alpine
```

**Important:** The deployment doc specified `docker.seadrive.org/seafileltd/seafile-pro-mc:13.0-latest` but that tag does not exist on the Seafile private registry. The 13.0 Pro image is on Docker Hub. The `latest` tag does exist on docker.seadrive.org (currently a newer version than 13.0).

### Storage
```
SEAF_SERVER_STORAGE_TYPE=disk    # Options: disk, s3, multiple
SEAFILE_VOLUME=/opt/seafile-data
SEAFILE_MYSQL_VOLUME=/opt/seafile-mysql/db
SEAFILE_CADDY_VOLUME=/opt/seafile-caddy
```

### Server identity
```
SEAFILE_SERVER_HOSTNAME=seafile.designflow.app
SEAFILE_SERVER_PROTOCOL=https    # Tells Caddy to handle HTTPS/TLS
TIME_ZONE=America/Sao_Paulo
JWT_PRIVATE_KEY=<64-char random string>   # Used to sign internal JWTs
```

### Database credentials
```
SEAFILE_MYSQL_DB_HOST=db         # Docker service name
SEAFILE_MYSQL_DB_USER=seafile
SEAFILE_MYSQL_DB_PASSWORD=<password>
SEAFILE_MYSQL_DB_CCNET_DB_NAME=ccnet_db
SEAFILE_MYSQL_DB_SEAFILE_DB_NAME=seafile_db
SEAFILE_MYSQL_DB_SEAHUB_DB_NAME=seahub_db
```

### Init-only variables (only used on first container start)
```
INIT_SEAFILE_ADMIN_EMAIL=u2giants@gmail.com
INIT_SEAFILE_ADMIN_PASSWORD=<password>        # Can be changed in UI after first start
INIT_SEAFILE_MYSQL_ROOT_PASSWORD=<password>   # MariaDB root password
```

### S3 storage (not yet configured — currently using disk)
```
# To enable S3, change SEAF_SERVER_STORAGE_TYPE=s3 and fill these in:
S3_COMMIT_BUCKET=<bucket>
S3_FS_BUCKET=<bucket>
S3_BLOCK_BUCKET=<bucket>
S3_KEY_ID=<key>
S3_SECRET_KEY=<secret>
S3_USE_V4_SIGNATURE=true
S3_AWS_REGION=us-east-1
S3_HOST=           # Leave empty for AWS; set for S3-compatible (e.g. Linode Object Storage)
S3_USE_HTTPS=true
S3_PATH_STYLE_REQUEST=false    # Set true for some S3-compatible providers
```

---

## /opt/seafile-data/seafile/conf/seahub_settings.py

The main Django settings file for Seahub (the web UI). Managed by Seafile's init process — edits persist across container restarts. Always restart the seafile container after editing.

**Current contents:**
```python
SECRET_KEY = "2aqy%o)8kxoix_0#jdz4uzi+r&cx+ix&8z#+w&uh^!y*(lhyp7"
TIME_ZONE = 'America/Sao_Paulo'
```

**Google OAuth SSO block to add** (see PENDING.md for how):
```python
ENABLE_OAUTH = True
OAUTH_ENABLE_INSECURE_TRANSPORT = False
OAUTH_CLIENT_ID = '<GOOGLE_CLIENT_ID>'
OAUTH_CLIENT_SECRET = '<GOOGLE_CLIENT_SECRET>'
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

---

## /opt/seafile-data/seafile/conf/seafile.conf

Minimal — Seafile auto-generates sensible defaults.
```ini
[fileserver]
port=8082
```

---

## /opt/seafile-data/seafile/conf/seafevents.conf

Controls background processing. Notable: the `[INDEX FILES]` section references Elasticsearch, which is NOT deployed in this installation. Full-text search is therefore not functional. To enable it, Elasticsearch would need to be added to the compose stack (see PENDING.md).
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
es_host = elasticsearch    # This host does not exist — search indexing will fail silently
es_port = 9200
enabled = true
interval = 10m
index_office_pdf = true

[FILE HISTORY]
enabled = true
suffix = md,txt,doc,docx,xls,xlsx,ppt,pptx,sdoc
```

---

## /opt/seafile-data/seafile/conf/seafdav.conf

WebDAV access is disabled.
```ini
[WEBDAV]
enabled = false
port = 8080
share_name = /seafdav
```
To enable WebDAV: set `enabled = true` and restart. No additional port needs opening — WebDAV traffic routes through Caddy on 443.

---

## Cron Jobs (root crontab)

```
0 3 * * *   MySQL dump of all databases → /opt/backups/seafile-db-YYYYMMDD.sql
0 4 * * *   Delete SQL files older than 30 days from /opt/backups/
```

---

## System Settings

| Setting | Value | Where set |
|---------|-------|-----------|
| `vm.max_map_count` | 262144 | `/etc/sysctl.conf` (for Elasticsearch, if ever deployed) |
| UFW firewall | 22, 80, 443 open | `ufw` |
| Docker boot start | enabled | `systemctl enable docker` |
| containerd boot start | enabled | `systemctl enable containerd` |

---

## Docker Registry

The Seafile private registry at `docker.seadrive.org` credentials (for pulling future images or the `latest` tag):
- Username: `seafile`
- Password: `zjkmid6rQibdZ=uJMuWS`

Login: `docker login docker.seadrive.org`

These are Seafile's published public credentials and may be rotated. Check https://customer.seafile.com/downloads/ for current credentials if login fails.
