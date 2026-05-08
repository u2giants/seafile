# Operations Guide

## Starting and Stopping

All commands run from `/opt/seafile/` as root (or with sudo).

### Start everything
```bash
cd /opt/seafile
docker compose -f seafile-server.yml -f caddy.yml up -d
```

### Stop everything (containers stop, data preserved)
```bash
cd /opt/seafile
docker compose -f seafile-server.yml -f caddy.yml down
```

### Restart all containers (e.g. after config change)
```bash
cd /opt/seafile
docker compose -f seafile-server.yml -f caddy.yml restart
```

### Restart only the Seafile app (e.g. after editing seahub_settings.py)
```bash
docker restart seafile
```

### Check container status
```bash
docker compose -f /opt/seafile/seafile-server.yml -f /opt/seafile/caddy.yml ps
```
All four containers should show `Up` and `(healthy)`.

### Containers start automatically on reboot
Docker is `systemctl enabled` — containers with `restart: unless-stopped` come back automatically after a server reboot. No manual action needed.

---

## Viewing Logs

### Live logs from all containers
```bash
cd /opt/seafile
docker compose -f seafile-server.yml -f caddy.yml logs -f
```

### Logs from a specific container
```bash
docker logs seafile          # Main Seafile app
docker logs seafile-caddy    # Caddy proxy / TLS
docker logs seafile-mysql    # Database
docker logs seafile-redis    # Cache
```

### Seafile application logs (inside container, more detailed)
```bash
ls /opt/seafile-data/seafile/logs/
# Key files:
#   seahub.log        — web UI access and errors
#   seafile.log       — file sync daemon
#   seafevents.log    — background jobs (search indexing, audit)
```

---

## Backup and Restore

### What's backed up automatically
A cron job runs daily at 3am and dumps all three MySQL databases:
```
/opt/backups/seafile-db-YYYYMMDD.sql
```
Files older than 30 days are deleted automatically (4am cleanup cron).

### Manual backup
```bash
docker exec seafile-mysql mysqldump \
  -u root -p$(grep INIT_SEAFILE_MYSQL_ROOT_PASSWORD /opt/seafile/.env | cut -d= -f2) \
  --all-databases > /opt/backups/seafile-db-manual-$(date +%Y%m%d%H%M%S).sql
```

### What backup does NOT cover
The SQL dump covers user accounts, sharing permissions, and library metadata — but NOT the actual file data. File data lives in `/opt/seafile-data/seafile/seafile-data/`. Back this up separately if using local disk storage. If S3 storage is configured, file data is in the S3 bucket and inherits S3 durability.

### Restore from SQL backup
```bash
# Stop seafile first
cd /opt/seafile && docker compose -f seafile-server.yml -f caddy.yml stop seafile

# Restore
docker exec -i seafile-mysql mysql \
  -u root -p$(grep INIT_SEAFILE_MYSQL_ROOT_PASSWORD /opt/seafile/.env | cut -d= -f2) \
  < /opt/backups/seafile-db-YYYYMMDD.sql

# Restart
docker compose -f seafile-server.yml -f caddy.yml start seafile
```

---

## TLS Certificate

Caddy handles Let's Encrypt certificates automatically. Certificates are stored at `/opt/seafile-caddy/certificates/` and auto-renewed before expiry. No manual action needed.

If the certificate fails to renew:
1. Ensure DNS still resolves: `dig seafile.designflow.app` should return `172.233.14.233`
2. Ensure port 80 is reachable (needed for ACME HTTP challenge)
3. Check Caddy logs: `docker logs seafile-caddy`

---

## Updating Seafile

### Check current version
```bash
docker exec seafile seafile-admin --version 2>/dev/null || docker exec seafile cat /opt/seafile/seafile-server-latest/VERSION
```

### Update to a new version
1. Check the Seafile changelog at https://manual.seafile.com for breaking changes
2. Edit `/opt/seafile/.env` and update the `SEAFILE_IMAGE` tag
3. Pull the new image and recreate the container:
```bash
cd /opt/seafile
docker compose -f seafile-server.yml -f caddy.yml pull seafile
docker compose -f seafile-server.yml -f caddy.yml up -d seafile
```
4. Watch logs for successful startup: `docker logs -f seafile`

---

## Seafile Admin Panel

Access at: https://seafile.designflow.app/sys/useradmin/

Login with `u2giants@gmail.com`. The admin panel lets you:
- View/create/delete user accounts
- View storage usage per user
- Check license status (System Info → Users limit)
- View audit logs
- Manage libraries

---

## Adding Users

### Via admin panel
Admin Panel → Users → Add User → enter email, password, set role.

### Via API
```bash
ADMIN_TOKEN=$(curl -s -d "username=u2giants@gmail.com&password=PASS" \
  https://seafile.designflow.app/api2/auth-token/ | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s -X PUT "https://seafile.designflow.app/api/v2.1/admin/users/newuser@example.com/" \
  -H "Authorization: Token $ADMIN_TOKEN" \
  -d "password=PASS&is_active=true"
```

---

## Checking the Seafile License

```bash
# Via web: Admin Panel → System Info → Users limit (should NOT be 3)
# Via file:
cat /opt/seafile-data/seafile-license.txt
```

If the license shows 3 users (trial mode):
1. Verify the file exists and is named exactly `seafile-license.txt` (case-sensitive)
2. Restart: `docker restart seafile`

---

## Cloudflare DNS

Zone: `designflow.app`  
Zone ID: `921eb133a3f7d5802780445b283f84ce`  
Cloudflare Account ID: `8303d11002766bf1cc36bf2f07ba6f20`

The DNS record must be **DNS-only (not proxied)** because Seafile's sync protocol breaks behind Cloudflare's proxy.

Current record:
- Name: `seafile` → `seafile.designflow.app`
- Type: A
- Content: `172.233.14.233`
- Proxied: No (grey cloud)
- Record ID: `2c1cdc08f9f79d9d668970854d9e15a8`

To manage via API (requires Cloudflare token):
```bash
CF_TOKEN="your-token"
ZONE_ID="921eb133a3f7d5802780445b283f84ce"
curl -s "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?name=seafile.designflow.app" \
  -H "Authorization: Bearer $CF_TOKEN"
```

---

## Troubleshooting

### 502 Bad Gateway
Seafile is still initializing. Wait 3–5 minutes after starting. Check: `docker logs -f seafile`

### "Seafile server started" never appears in logs
Check for errors: `docker logs seafile 2>&1 | grep -i error`  
Common causes: database connection failure, missing JWT_PRIVATE_KEY, license file issues.

### TLS certificate error in browser
DNS not propagated yet, or Caddy couldn't reach Let's Encrypt. Check Caddy logs.

### Login fails with correct password
Check seahub_settings.py for syntax errors, especially after editing OAuth config.  
`docker restart seafile` after any config change.

### Container keeps restarting
`docker logs seafile` — look at the last few lines before each restart for the error.
