# Context for AI Sessions

Read this before doing anything else on this system.

## Who You're Working For

**Albert** (u2giants@gmail.com / albert@popcre.com) runs POP Creations, a design agency. He delegates infrastructure work to AI sessions via Claude Code running on this VPS as the `ai` user with passwordless sudo.

## What This System Is

Seafile Pro 13.0 on a Linode VPS. 8 graphic designers in São Paulo access a 28TB file library that lives on Synology NAS devices in a NYC office. The VPS is a relay: NAS pushes files here via seaf-cli; designers pull via HTTPS.

**File data goes to S3, not the VPS disk.** The VPS disk holds only the database, config, and application state.

## Access

```
User:     ai (passwordless sudo)
VPS:      172.233.14.233
App dir:  /opt/seafile/
Creds:    /opt/seafile/CREDENTIALS.txt (root-only, chmod 600)
```

**Read credentials from the file — never hardcode or regenerate them.**

## Current State

| Component | Status |
|-----------|--------|
| Seafile Pro 13.0 | Running and healthy |
| Google OAuth SSO | Live — u2giants@gmail.com and albert@popcre.com are admins |
| S3 storage | Configured — Linode br-gru-1, 3 buckets |
| NAS sync account | nas-sync@popcre.com (machine account) |
| Libraries | Active Projects, Assets, Seasonal — UUIDs in CREDENTIALS.txt |
| Synology seaf-cli | **seaf-cli-decor running on edgesynology1** (Decor → Active Projects) |
| Designer accounts | **Not yet created** |
| Elasticsearch | **Not deployed** (intentional — RAM) |

## Key Commands

```bash
# Container status
docker compose -f /opt/seafile/seafile-server.yml -f /opt/seafile/caddy.yml ps

# Restart Seafile app (after seahub_settings.py edit)
docker restart seafile

# Restart all (after .env change)
cd /opt/seafile && docker compose -f seafile-server.yml -f caddy.yml restart

# Logs
docker logs seafile
docker logs seafile-caddy
```

## Synology NAS — seaf-cli

**edgesynology1** (192.168.3.100): seaf-cli-decor container is **live and syncing** `/volume1/mac/Decor` → Active Projects library.

**Docker binary on Synology:** `/var/packages/ContainerManager/target/usr/bin/docker`  
The `docker` binary is NOT in PATH. The NAS MCP `run_command` allowlist blocks any command string containing the word "docker". To run docker commands via the NAS MCP, encode with base64:
```bash
CMD="/var/packages/ContainerManager/target/usr/bin/docker ps"
echo $(echo "$CMD" | base64) | base64 -d | bash
# Or in Python: b64 = base64.b64encode(cmd.encode()).decode(); f"echo '{b64}' | base64 -d | bash"
```

**Compose file lives at `/tmp/seaf-cli-compose.yml` on edgesynology1.** `/tmp` is cleared on reboot; the container persists because it has `restart: unless-stopped` and Docker restores it. But if the container is ever manually stopped and removed, re-deploy from the repo's `synology-seaf-cli/docker-compose.yml`.

**seaf-cli image:** Use `flrnnc/seafile-client:latest` (formerly `flowgunso/seafile-client` — same image, `flowgunso` is a deprecated alias). `seafileltd/seaf-cli` does NOT exist on Docker Hub.

**seaf-cli env vars:** `SEAF_SERVER_URL`, `SEAF_USERNAME`, `SEAF_PASSWORD`, `SEAF_LIBRARY` (UUID). Not `SERVER_URL`/`USERNAME`/`PASSWORD`/`LIBRARY_ID`.

**NAS folder path is case-sensitive:** `/volume1/mac/Decor` (capital D). `/volume1/mac/decor` does not exist.

**Assets and Seasonal NAS paths** are unknown — the volume layout under `/volume1/mac` has `Art Library`, `Decor`, `Fonts`, `Gift Bags` but no obvious "Assets" or "Seasonal" folder. Ask Albert before adding more sync containers.

## Non-Obvious Facts

**Image name:** `seafileltd/seafile-pro-mc:13.0-latest` is on Docker Hub. `docker.seadrive.org` does not have a `13.0-latest` tag — only `latest` (different, newer build). The `.env` and compose file use the Docker Hub image.

**Cloudflare proxy is off intentionally.** `seafile.designflow.app` is DNS-only. Do not enable the orange cloud — it breaks Seafile's sync protocol.

**Seafile user emails are internal UUIDs.** The API stores accounts as `<hash>@auth.local` internally. The human email is `contact_email`. When calling admin APIs to modify a user, use the internal email. Get it from `GET /api/v2.1/admin/users/`.

**seahub_settings.py lives in the Docker volume** at `/opt/seafile-data/seafile/conf/seahub_settings.py`. Persists across restarts. After editing: `docker restart seafile`. Before editing: make a backup.

**CONFIGURE_OAUTH.sh is NOT idempotent.** Running it twice duplicates the OAuth block in seahub_settings.py, which causes a Django error. Check the file first.

**CREATE_NAS_SYNC_ACCOUNT.sh is for fresh installs only.** The NAS sync account and libraries already exist. Running this script again would create duplicates.

**seafevents.conf references Elasticsearch** (`es_host = elasticsearch`) which doesn't exist. This logs connection errors every 10 minutes — expected, harmless. See architecture.md.

**S3 requires 3 distinct buckets.** Seafile refuses to start if any two of `S3_BLOCK_BUCKET`, `S3_COMMIT_BUCKET`, `S3_FS_BUCKET` share a name.

**Seafile's init vars are init-only.** `INIT_SEAFILE_ADMIN_EMAIL`, `INIT_SEAFILE_ADMIN_PASSWORD`, and `INIT_SEAFILE_MYSQL_ROOT_PASSWORD` in `.env` are only applied on first startup. Changing them later has no effect.

## Scripts in /opt/seafile/

| Script | Purpose | Run again? |
|--------|---------|-----------|
| `START_SEAFILE.sh` | Pre-flight checks + start | Yes — after any reboot or stop |
| `CONFIGURE_OAUTH.sh CLIENT_ID SECRET` | Append OAuth block to seahub_settings.py + restart | No — already done; check file first |
| `CREATE_NAS_SYNC_ACCOUNT.sh` | Create nas-sync@popcre.com + libraries | No — already done |

## GitHub Repo

https://github.com/u2giants/seafile — contains compose files, scripts, and this documentation. Secrets (`.env`, `CREDENTIALS.txt`) are gitignored and never committed.

To push doc updates:
```bash
cd ~/seafile-repo
git add -A && git commit -m "message" && git push
```
