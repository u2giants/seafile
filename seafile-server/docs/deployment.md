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

## seaf-cli Containers

The seaf-cli containers use `ghcr.io/u2giants/seafile:seaf-cli-latest`. They can run on the NAS or on the Windows workstation — see `seafile-server/docs/architecture.md` for the comparison. Both deployments use the same image and the same `docker-compose.yml` structure; only the source volume type differs.

Currently running on: **NAS (edgesynology1)**.

### NAS deployment

Managed via the NAS MCP (not SSH). All docker commands must be base64-encoded — see AGENTS.md.

### Release a code change to seaf-cli

When `synology-seaf-cli/Dockerfile`, `entrypoint.py`, or `seaf-entrypoint.py` change:

1. Commit to `main` — GitHub Actions builds and pushes the wrapper image automatically
2. Wait for CI: https://github.com/u2giants/seafile/actions (workflow: `seaf-cli image`)
3. Pull and recreate on edgesynology1 via NAS MCP:

```bash
# docker pull ghcr.io/u2giants/seafile:seaf-cli-latest
CMD="docker pull ghcr.io/u2giants/seafile:seaf-cli-latest"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'

# docker compose -f /tmp/seaf-cli-compose.yml up -d --force-recreate
CMD="/var/packages/ContainerManager/target/usr/bin/docker compose -f /tmp/seaf-cli-compose.yml up -d --force-recreate"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'
```

### Release a compose-only change

When only `synology-seaf-cli/docker-compose.yml` changes (environment, volumes — no image rebuild needed):

1. Commit to `main` and push
2. Write the updated compose file to `/tmp/seaf-cli-compose.yml` on edgesynology1 via NAS MCP (base64+tee)
3. Recreate containers:
```bash
CMD="/var/packages/ContainerManager/target/usr/bin/docker compose -f /tmp/seaf-cli-compose.yml up -d"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'
```

### Windows workstation deployment

Prerequisites on the Windows machine: WSL2 enabled, Docker Desktop installed with "Start Docker Desktop when you log in" enabled.

```powershell
# Run once as Administrator from the windows-workstation/ directory
.\setup.ps1
```

`setup.ps1` installs the PopDAM Windows Agent (downloads from GitHub releases if not already present), writes `.env` credentials, starts the seaf-cli containers, and registers a login-triggered scheduled task.

**Cutover procedure (switching from NAS to Windows):**
1. Run `setup.ps1` on the Windows machine and verify `docker ps` shows both containers healthy
2. Stop the NAS containers via NAS MCP:
```bash
CMD="/var/packages/ContainerManager/target/usr/bin/docker compose -f /tmp/seaf-cli-compose.yml stop"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'
```

**Machine replacement:** Copy the `windows-workstation/` folder to the new machine, run `setup.ps1`. Sync state rebuilds from scratch (seaf-daemon re-hashes all files on first start — expect 200-300% CPU for several hours).

**Credentials needed for setup.ps1:**
- Seafile: `SEAF_USERNAME` / `SEAF_PASSWORD` — from `/opt/seafile/CREDENTIALS.txt` on VPS (nas-sync@popcre.com)
- NAS SMB: `NAS_USERNAME` / `NAS_PASSWORD` — a Synology local account with read access to the `mac` shared folder on edgesynology1

---

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

### Restore NAS sync — the seaf-cli containers were removed (2026-06-05)
As of 2026-06-05 both NAS seaf-cli containers are **gone** from edgesynology1 (removed, not stopped — `docker ps -a` lists neither). Sync is down. The data/staging volumes and the image survive, so re-deploying `synology-seaf-cli/docker-compose.yml` restores sync without a full re-hash. See AGENTS.md → Critical Incident Log. Decide between restoring on the NAS or doing the Windows cutover below — never run both.

### Windows workstation cutover (optional)
`windows-workstation/setup.ps1` is ready. Run it on the Windows rendering machine to move the seaf-cli upload work off the NAS. See Windows workstation deployment above. Only one host may run seaf-cli at a time.

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
