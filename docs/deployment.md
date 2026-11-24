---
summary: Deploy and rollback paths: verify the live VPS, start/stop, server updates, nas-settings release, NAS seaf-cli deploy and owner-run recreate, DNS, TLS, backups.
kind: living
status: current
read-when: deploying, recreating, rolling back or verifying any part of the stack
---

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

Before any restart, compare the active account count with the capacity and expiration in the [effective license](configuration.md#effective-seafile-license). The completed [November 2026 recovery](plan-license-recovery-2026-11.md) explains the former 10-user/11-account startup failure; do not rerun its historical swap.

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

## Seafile Server Updates (Same 13.0 Line)

`SEAFILE_IMAGE` is the floating `seafileltd/seafile-pro-mc:13.0-latest` tag and nothing on the VPS pulls it, so the server only moves when someone runs the steps below. `curl -s https://seafile.designflow.app/api2/server-info/` reports the running version; compare it with the `13.0.*` tags on Docker Hub before assuming the server is current. Each upgrade is tracked on one issue that holds the reviewed plan and the live proof (13.0.21 → 13.0.30: issue #30).

A move inside the 13.0 line is what Seafile's manual calls a maintenance upgrade: no new compose file and no `.env` change. Run everything below as root from `/opt/seafile`.

1. **Seats.** A recreate is a restart, so the [license check](#start--stop--restart) applies: active accounts must not exceed `MaxUsers`.
2. **Backup.** Before any file changes, take a [manual database dump](#manual) and archive what Git cannot rebuild: `/opt/seafile/.env`, the live configuration, the deployed overrides and the license. The archive is root-only because it holds secrets, and it is what rollback puts back.

   ```bash
   (umask 077; tar -czf /opt/backups/seafile-conf-manual-$(date +%Y%m%d%H%M%S).tar.gz -C / \
     opt/seafile/.env \
     opt/seafile-data/seafile/conf \
     opt/seafile-data/seafile/seahub-data/custom/templates \
     opt/seafile-data/seafile/seafile-license.txt)
   ```

3. **Templates.** Download the target release under its explicit version tag first: that touches no running container and does not move `13.0-latest`. Then diff each upstream file behind an override in `custom-templates/` between the running container and the new image.

   ```bash
   NEW=13.0.30                                   # the target release
   RUNNING=$(docker exec seafile printenv SEAFILE_VERSION)
   TMP=$(mktemp -d)
   docker rm -f seaf-tmp >/dev/null 2>&1         # a container left by an interrupted run
   docker pull "seafileltd/seafile-pro-mc:$NEW"
   for f in react_app.html registration/login.html sysadmin/sysadmin_react_app.html sysadmin/sudo_mode.html; do
     docker create --name seaf-tmp "seafileltd/seafile-pro-mc:$NEW" >/dev/null
     rm -f "$TMP/new" "$TMP/old"
     docker cp "seaf-tmp:/opt/seafile/seafile-pro-server-$NEW/seahub/seahub/templates/$f" "$TMP/new"
     docker rm seaf-tmp >/dev/null
     docker exec seafile cat "/opt/seafile/seafile-pro-server-$RUNNING/seahub/seahub/templates/$f" > "$TMP/old"
     if [ ! -s "$TMP/new" ] || [ ! -s "$TMP/old" ]; then echo "$f: NOT COMPARED (copy or read failed)"
     elif diff "$TMP/old" "$TMP/new" > /dev/null; then echo "$f: upstream unchanged"
     else echo "$f: UPSTREAM CHANGED"; fi
   done
   rm -rf "$TMP"
   ```

   If upstream changed, re-apply our addition to the new upstream file in `custom-templates/` and land it through its own pull request before going further (see `custom-templates/README.md`). Nothing is deployed in this step.
4. **Drift.** Confirm `/opt/seafile/*.yml` still match the repo and that the rendered Compose environment still matches the running container, so the recreate changes nothing but the image.
5. **Review.** The recreate is a production action. An assigned AI reviewer's exact-head APPROVE must cover the head that documents these steps, and `ai-task-gates check --before production --reviewer-approval <report>` must open before it runs. The reviewed plan (the tracking issue) names the target release and the image digest it saw; the check below compares against that digest.

Then, in the same shell:

```bash
# Name the image the running container was started from (by ID, never by the floating
# tag, which a later pull can move), so it stays reachable for rollback under its own version
RUNNING=$(docker exec seafile printenv SEAFILE_VERSION)
docker tag "$(docker inspect -f '{{.Image}}' seafile)" "seafileltd/seafile-pro-mc:$RUNNING"

docker compose -f seafile-server.yml -f caddy.yml pull seafile
# Must print the digest named in the reviewed plan. A floating tag can move at any
# time; a different digest is a release nobody reviewed, so stop here.
docker image inspect seafileltd/seafile-pro-mc:13.0-latest --format '{{index .RepoDigests 0}}'

# Recreates the seafile container only and returns once it is healthy
docker compose -f seafile-server.yml -f caddy.yml up -d --no-deps --wait --wait-timeout 300 seafile
```

If step 3 changed an override, copy the landed file into `/opt/seafile-data/seafile/seahub-data/custom/templates/` between the digest check and the recreate. The recreate restarts Seahub, so no separate restart is needed; without that copy the new server would run with the old override.

`--no-deps` leaves the database, cache and proxy containers untouched. Prove it live before closing the issue: `server-info` shows the new version, the sign-in page loads, the four overridden screens render, `docker logs seafile` has no `users exceeds limit`, and the NAS sync container reconnects.

**Rollback:** first put the step 2 archive back (`tar -C / -xzf /opt/backups/seafile-conf-manual-<timestamp>.tar.gz`), which restores the overrides and `.env` as they were before anything changed. Then run the same `up -d --no-deps --wait seafile` with `SEAFILE_IMAGE=seafileltd/seafile-pro-mc:$RUNNING` on the command line, where `$RUNNING` is the version that ran before the upgrade, never `$NEW`. [Restore](#restore) the pre-upgrade dump only if the new version changed the database in a way the old one cannot read.

Never use this procedure for a major version (13 → 14). That is a migration with Seafile's own upgrade notes, new configuration and its own reviewer-approved plan.

## nas-settings Panel

The `nas-settings` container runs the **CI-built** image `ghcr.io/u2giants/seafile:nas-settings-latest` (built + published by `.github/workflows/nas-settings-image.yml`). It is deployed from `seafile-server/nas-settings.yml` in the repo (not in `COMPOSE_FILE`) and managed separately. **Do not build it on the VPS** — always pull the published image.

### Release a code change to nas-settings

When anything under `seafile-server/nas-settings/` changes:

1. Merge via pull request — GitHub Actions (`nas-settings image`) tests, builds, and pushes `nas-settings-latest` + `nas-settings-sha-<commit>` to GHCR.
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
NAS status reporter. After the 2026-06-16 multi-library heartbeat fix, one POST
roughly every 30 seconds is expected for each synced library.

**Rollback:** pin `image:` in `nas-settings.yml` to a prior `ghcr.io/u2giants/seafile:nas-settings-sha-<older-commit>` and `up -d` — never rebuild on the host.

**Note:** Seahub template overrides (`seafile-server/custom-templates/`) are *not* part of this image — they deploy by copying into the Seahub custom dir + `docker restart seafile` (see `custom-templates/README.md`).

## seaf-cli Container

The seaf-cli container uses `ghcr.io/u2giants/seafile:seaf-cli-latest` and runs on the `edgesynology1` NAS.

Currently running on: **NAS (edgesynology1)**.

### NAS deployment

The canonical NAS deploy procedure — stack directory `/volume1/docker/seaf-cli/`, its `.env`, Watchtower auto-updates, and the 2026-06-21 incident that made it canonical — is [`synology-seaf-cli/README.md`](../synology-seaf-cli/README.md); read that first.

The `ai` account (`ssh edge1` from the VPS) owns `/volume1/docker/seaf-cli/` but has **no** admin access on the NAS, and the owner ruled on 2026-10-26 that AI admin access will not be restored. AI stages file changes (copy the current repo `docker-compose.yml` into the stack directory) and hands the owner the exact `docker compose pull && docker compose up -d` command to run. Docker on Synology lives at `/var/packages/ContainerManager/target/usr/bin/docker` and is not in the default PATH.

Do not reuse an old `/tmp/seaf-cli-compose.yml` or `/tmp/seaf-cli-compose-codex.yml`: stale two-service compose files have existed there, and `/tmp` is wiped on NAS reboot. Verify any staged compose file with `docker compose config --services` — the expected output is exactly `seaf-cli`.

### Release a code change to seaf-cli

When `synology-seaf-cli/Dockerfile`, `entrypoint.py`, or `seaf-entrypoint.py` change:

1. Commit via pull request — GitHub Actions builds and pushes the wrapper image automatically.
2. Wait for CI: https://github.com/u2giants/seafile/actions (workflow: `seaf-cli image`).
3. Routine image updates deploy themselves via Watchtower. If Watchtower cannot be waited on, stage the current compose file in the stack directory and hand the owner the exact `docker compose pull && docker compose up -d` command.

If a manual recreate is needed and Compose fails because the existing `seaf-cli` container name is in use, the owner removes only that container and runs `up -d` again. The named `seaf-cli-data` volume preserves sync state; never delete it for a failed-clone retry (see [incidents](incidents.md) and [idiosyncrasies](idiosyncrasies.md)).

### Release a compose-only change

When only `synology-seaf-cli/docker-compose.yml` changes (environment, volumes — no image rebuild needed):

1. Commit via pull request.
2. Copy the updated compose file to `/volume1/docker/seaf-cli/docker-compose.yml` on `edgesynology1` over SSH.
3. Hand the owner the exact `docker compose up -d` command; never run it as `ai` (no sudo), and never pass credentials via shell env — the stack's `.env` is loaded by `env_file:`.

### Automatic
Daily cron at 3am dumps all MariaDB databases to `/opt/backups/seafile-db-YYYYMMDD.sql`. Files older than 30 days are deleted at 4am.

### Manual
Run as root. The password is read inside the database container from its own environment, so it never appears in a command line.

```bash
(umask 077; docker exec seafile-mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -u root --all-databases' \
  > /opt/backups/seafile-db-manual-$(date +%Y%m%d%H%M%S).sql)
```

Check the last line of the dump for `Dump completed` before relying on it.

### What is NOT backed up
File data lives in S3 — inherits Linode's durability. The SQL backup covers only metadata: accounts, sharing, library references, audit logs. Losing the SQL without a backup means losing user accounts and permissions, but file data in S3 remains intact.

### Restore
```bash
cd /opt/seafile && docker compose -f seafile-server.yml -f caddy.yml stop seafile
docker exec -i seafile-mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -u root' \
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

> Live state and the authoritative pending list are in [`pending-work.md`](pending-work.md). As of 2026-06-16 the NAS `seaf-cli` container has been recreated on the current image, is healthy, and the recreated `nas-settings` container is receiving one status POST per synced library roughly every 30 seconds.

### NAS-agent image already picked up

The 2026-06-11 recreate pulled `ghcr.io/u2giants/seafile:seaf-cli-latest` and started the single `seaf-cli` service from current compose. If a future status payload lacks fields such as `folder_size_cache`, or if new `@eaDir` content keeps uploading after `seafile-ignore.txt` is present, first verify the running image digest and that the active compose config contains only the `seaf-cli` service. Historical `/tmp` staging (`/tmp/seaf-cli-compose-codex.yml`, `/tmp/.env`) is retired and wiped on reboot; the canonical stack directory is `/volume1/docker/seaf-cli/` with its own `.env` (see the [seaf-cli README](../synology-seaf-cli/README.md)).

### Designer user accounts
Send designers `https://seafile.designflow.app`. Automatic account creation on first M365 SSO login is **off** (`REMOTE_USER_CREATE_UNKNOWN_USER = False`, see [incidents](incidents.md)): onboard by pre-creating the user in the admin UI and adding their Microsoft `social_auth_usersocialauth` link before their first sign-in, and buy license capacity first — all 12 seats are used. Albert then shares the relevant libraries via the web UI.

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
