# Deployment

## Verify Live VPS

The live Seafile VPS is `172.233.14.233` and currently identifies as `seafile-br`.
Other hosts may have stale `/worksp/seafile` clones but no running Seafile stack.
Before a deploy, verify the target:

```bash
hostname
ls -la /opt/seafile
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -E 'seafile|caddy|nas-settings'
```

Expected containers include `seafile`, `seafile-mysql`, `seafile-redis`,
`seafile-caddy`, and `nas-settings`. If those are absent, stop; it is not the
live VPS.

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

The `nas-settings` container runs the **CI-built** image `ghcr.io/u2giants/seafile:nas-settings-latest` (built + published by `.github/workflows/nas-settings-image.yml`). It is deployed from `seafile-server/nas-settings.yml` in the repo (not in `COMPOSE_FILE`) and managed separately. **Do not build it on the VPS** — pull the published image (§25 model; see AGENTS.md → Deployment).

### Release a code change to nas-settings

When anything under `seafile-server/nas-settings/` changes:

1. Commit to `main` — GitHub Actions (`nas-settings image`) tests, builds, and pushes `nas-settings-latest` + `nas-settings-sha-<commit>` to GHCR.
2. Wait for CI: https://github.com/u2giants/seafile/actions (workflow: `nas-settings image`).
3. Pull and recreate on the VPS:

```bash
cd /opt/seafile

docker compose \
  --env-file /opt/seafile/.env \
  -f /home/ai/seafile-repo/seafile-server/nas-settings.yml \
  pull nas-settings

docker compose \
  --env-file /opt/seafile/.env \
  -f /home/ai/seafile-repo/seafile-server/nas-settings.yml \
  up -d --force-recreate nas-settings

docker logs --tail 80 nas-settings
```

Healthy logs include repeated `POST /api/status HTTP/1.1" 200` entries from the
NAS status reporter. After the 2026-06-16 multi-library heartbeat fix, three
POSTs roughly every 30 seconds are expected: one per synced library.

**Rollback:** pin `image:` in `nas-settings.yml` to a prior `ghcr.io/u2giants/seafile:nas-settings-sha-<older-commit>` and `up -d` — never rebuild on the host.

**Note:** Seahub template overrides (`seafile-server/custom-templates/`) are *not* part of this image — they deploy by copying into the Seahub custom dir + `docker restart seafile` (see `custom-templates/README.md`).

## seaf-cli Container

The seaf-cli container uses `ghcr.io/u2giants/seafile:seaf-cli-latest`. It can run on the NAS or on the Windows workstation — see `docs/architecture.md` for the comparison. Both deployments use the same image; only the source volume type differs.

Currently running on: **NAS (edgesynology1)**.

### NAS deployment

NAS deploys/recreates are done from the VPS over SSH:

```bash
ssh edge1
```

That logs in to `edgesynology1` as `ai`. Docker is not in PATH on Synology; use `/var/packages/ContainerManager/target/usr/bin/docker`. The `ai` account has passwordless sudo only for that Docker binary.

Do not reuse an old `/tmp/seaf-cli-compose.yml` blindly. A stale two-service compose file has existed on the NAS; stage the current repo file and verify it before `up`:

```bash
DOCKER=/var/packages/ContainerManager/target/usr/bin/docker
sudo -n $DOCKER compose -f /tmp/seaf-cli-compose-codex.yml --env-file /tmp/.env config --services
# expected: seaf-cli
```

### Release a code change to seaf-cli

When `synology-seaf-cli/Dockerfile`, `entrypoint.py`, or `seaf-entrypoint.py` change:

1. Commit to `main` — GitHub Actions builds and pushes the wrapper image automatically
2. Wait for CI: https://github.com/u2giants/seafile/actions (workflow: `seaf-cli image`)
3. Pull and recreate on `edgesynology1` over SSH:

```bash
DOCKER=/var/packages/ContainerManager/target/usr/bin/docker

# Rebuild /tmp/.env from the running container's env if needed; this avoids typing secrets.
sudo -n $DOCKER inspect seaf-cli \
  --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -E '^(SEAF_USERNAME|SEAF_PASSWORD|SEAF_STATUS_TOKEN)=' | sudo -n tee /tmp/.env >/dev/null

# Stage the current synology-seaf-cli/docker-compose.yml as /tmp/seaf-cli-compose-codex.yml first.
sudo -n $DOCKER pull ghcr.io/u2giants/seafile:seaf-cli-latest
sudo -n $DOCKER compose -f /tmp/seaf-cli-compose-codex.yml --env-file /tmp/.env up -d
```

If Compose fails because the existing `/seaf-cli` container name is already in use, remove only that container and run `up -d` again. The named `seaf-cli-data` volume preserves sync state:

```bash
sudo -n $DOCKER rm -f seaf-cli
sudo -n $DOCKER compose -f /tmp/seaf-cli-compose-codex.yml --env-file /tmp/.env up -d
```

### Release a compose-only change

When only `synology-seaf-cli/docker-compose.yml` changes (environment, volumes — no image rebuild needed):

1. Commit to `main` and push
2. Write the updated compose file to `/tmp/seaf-cli-compose-codex.yml` on `edgesynology1`
3. Recreate the container over SSH:
```bash
DOCKER=/var/packages/ContainerManager/target/usr/bin/docker
sudo -n $DOCKER compose -f /tmp/seaf-cli-compose-codex.yml --env-file /tmp/.env up -d
```

### Windows workstation deployment

The Windows compose still reflects the older per-library/CIFS layout and was not validated during the 2026-06-11 NAS recovery. Treat this cutover as a separate migration: inspect `windows-workstation/docker-compose.yml` against the current `synology-seaf-cli/entrypoint.py` before stopping the NAS container.

Prerequisites on the Windows machine: WSL2 enabled, Docker Desktop installed with "Start Docker Desktop when you log in" enabled.

```powershell
# Run once as Administrator from the windows-workstation/ directory
.\setup.ps1
```

`setup.ps1` installs the PopDAM Windows Agent (downloads from GitHub releases if not already present), writes `.env` credentials, starts the seaf-cli containers, and registers a login-triggered scheduled task.

**Cutover procedure (switching from NAS to Windows):**
1. Run `setup.ps1` on the Windows machine and verify `docker ps` shows the seaf-cli containers healthy
2. Stop the NAS container over SSH on `edgesynology1`:
```bash
DOCKER=/var/packages/ContainerManager/target/usr/bin/docker
sudo -n $DOCKER compose -f /tmp/seaf-cli-compose-codex.yml --env-file /tmp/.env stop
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

> Live state and the authoritative pending list are in `AGENTS.md` → Pending work. As of 2026-06-16 the NAS `seaf-cli` container has been recreated on the current image, is healthy, and the recreated `nas-settings` container is receiving three per-library status POSTs roughly every 30 seconds.

### NAS-agent image already picked up

The 2026-06-11 recreate pulled `ghcr.io/u2giants/seafile:seaf-cli-latest` and started the single `seaf-cli` service from current compose. If a future status payload lacks fields such as `folder_size_cache`, or if `@eaDir` folders still appear in Seafile after a refresh, first verify the running image digest and that the active compose config contains only the `seaf-cli` service. `/tmp` is wiped on reboot, so `/tmp/seaf-cli-compose-codex.yml` and `/tmp/.env` may need re-staging before a future recreate.

### Windows workstation cutover (optional)
`windows-workstation/setup.ps1` exists but the cutover was not validated against the current single-container NAS sync model. Review the Windows compose/runtime path first. Only one host may run seaf-cli for a library at a time.

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
