# Deployment

## Start / Stop / Restart

All commands from `/opt/seafile/` as root.

```bash
# Start (or bring back up after a stop)
cd /opt/seafile && docker compose -f seafile-server.yml -f caddy.yml up -d

# Stop (containers stop, all data preserved)
cd /opt/seafile && docker compose -f seafile-server.yml -f caddy.yml down

# Restart all (e.g. after .env change)
cd /opt/seafile && docker compose -f seafile-server.yml -f caddy.yml restart

# Restart Seafile app only (e.g. after editing seahub_settings.py)
docker restart seafile

# Status
docker compose -f /opt/seafile/seafile-server.yml -f /opt/seafile/caddy.yml ps
```

All containers have `restart: unless-stopped` — they come back automatically after a reboot.

## nas-settings Panel

The `nas-settings` container is deployed from `seafile-server/nas-settings.yml` in the repo (not included in `COMPOSE_FILE` in `.env`). It is managed separately:

```bash
# Start / restart
cd /opt/seafile && docker compose \
  -f seafile-server.yml -f caddy.yml \
  -f /home/ai/seafile-repo/seafile-server/nas-settings.yml \
  up -d nas-settings

# Rebuild after code changes to seafile-server/nas-settings/
cd /home/ai/seafile-repo/seafile-server && docker compose -f nas-settings.yml build nas-settings
# Then restart as above
```

**Note:** The build context in `nas-settings.yml` is `./nas-settings` (relative to the compose file). Run the build from the `seafile-server/` directory, not from `/opt/seafile/`.

## First-Time Deployment

Use `START_SEAFILE.sh` which runs pre-flight checks before starting:

```bash
sudo bash /opt/seafile/START_SEAFILE.sh
```

Pre-flight checks: DNS resolves to this server's IP, license file exists. Do not bypass these.

**Prerequisites before first start:**
1. DNS A record `seafile.designflow.app → 172.233.14.233` (DNS-only, no proxy)
2. `/opt/seafile-data/seafile-license.txt` present
3. `.env` fully configured (copy from `.env.example`, fill all values)

## Updating Seafile

1. Check https://manual.seafile.com for breaking changes between versions
2. Edit `SEAFILE_IMAGE` in `/opt/seafile/.env`
3. Pull and recreate:
```bash
cd /opt/seafile
docker compose -f seafile-server.yml -f caddy.yml pull seafile
docker compose -f seafile-server.yml -f caddy.yml up -d --force-recreate seafile
docker logs -f seafile   # watch for "Seafile server started"
```

4. After a Seafile upgrade, diff the new `sysadmin/sysadmin_react_app.html` against the override in `seahub-data/custom/templates/` — the custom template is a full copy of Seafile's file plus the nav injection script, so upstream changes won't apply automatically.

## Backup

### Automatic
Daily cron at 3am dumps all MariaDB databases to `/opt/backups/seafile-db-YYYYMMDD.sql`. Files older than 30 days are deleted at 4am.

### Manual
```bash
docker exec seafile-mysql mysqldump \
  -u root -p$(grep INIT_SEAFILE_MYSQL_ROOT_PASSWORD /opt/seafile/.env | cut -d= -f2) \
  --all-databases > /opt/backups/seafile-db-manual-$(date +%Y%m%d%H%M%S).sql
```

### What is NOT backed up
File data lives in S3 — inherits Linode's durability. The SQL backup covers only metadata: accounts, sharing, library references, audit logs. Losing the SQL without a backup means losing user accounts and permissions, but file data in S3 remains intact.

### Restore
```bash
cd /opt/seafile && docker compose -f seafile-server.yml -f caddy.yml stop seafile
docker exec -i seafile-mysql mysql \
  -u root -p$(grep INIT_SEAFILE_MYSQL_ROOT_PASSWORD /opt/seafile/.env | cut -d= -f2) \
  < /opt/backups/seafile-db-YYYYMMDD.sql
docker compose -f seafile-server.yml -f caddy.yml start seafile
```

## DNS

Zone: `designflow.app` · Zone ID: `921eb133a3f7d5802780445b283f84ce`

Current record:
```
seafile.designflow.app  A  172.233.14.233  proxied=false  TTL=auto
Record ID: 2c1cdc08f9f79d9d668970854d9e15a8
```

**The Cloudflare proxy must stay off.** See [architecture.md](architecture.md) for why.

To manage via Cloudflare API (need a bearer token from Albert):
```bash
curl -s "https://api.cloudflare.com/client/v4/zones/921eb133a3f7d5802780445b283f84ce/dns_records" \
  -H "Authorization: Bearer $CF_TOKEN"
```

## TLS

Caddy manages Let's Encrypt automatically. Certificates auto-renew. No action needed unless renewal fails.

If renewal fails: verify DNS still resolves correctly and port 80 is reachable (used for ACME HTTP challenge), then check `docker logs seafile-caddy`.

## Remaining Work

### Designer user accounts
Send designers `https://seafile.designflow.app` — accounts are created automatically on first M365 SSO login (requires a POP Creations Microsoft account in the tenant). Albert then shares the relevant libraries via the web UI.

To share a library: log in → open library → Share → Share to User → enter designer email → Read/Write.

### Elasticsearch (optional)
Full-text search inside file contents. Not deployed due to RAM constraints on a 4GB server. If the server is upgraded:
```bash
cd /opt/seafile
wget https://manual.seafile.com/13.0/repo/docker/pro/elasticsearch.yml
# Add elasticsearch.yml to COMPOSE_FILE in .env
docker compose -f seafile-server.yml -f caddy.yml -f elasticsearch.yml up -d
```
`vm.max_map_count=262144` is already set. Monitor RAM — Elasticsearch needs ~2GB minimum.
