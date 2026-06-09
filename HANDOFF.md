# HANDOFF

Last updated: 2026-06-09. Read `AGENTS.md` first, then this file.

Delete `HANDOFF.md` only after the Synology `seaf-cli` containers are recreated with the latest image and cached folder-size data is visible in `nas-settings`.

## What was being built or fixed and why

The current unfinished work is the NAS-agent side of the latest `seaf-cli` image changes:

- sync schedule enforcement from the NAS Settings page
- cached recursive NAS folder-size reporting
- related live status fields

The VPS `nas-settings` panel image is already updated. The NAS containers are still reporting current heartbeats, but their status payload does not yet include `folder_size_cache`, so they have not picked up the newest NAS-agent image.

## Fully done

- `AGENTS.md` has been rewritten as the canonical operating guide and documentation router.
- The canonical topic docs were moved to top-level `docs/`:
  - `docs/architecture.md`
  - `docs/configuration.md`
  - `docs/deployment.md`
  - `docs/development.md`
- `README.md`, `CLAUDE.md`, ignore files, and relevant folder READMEs were updated to match the new documentation roles.
- Microsoft SSO is live and working.
- Active live Seafile users verified from MariaDB on 2026-06-09:
  - `4cba3f5721f7436fbe06a2b154ee296a@auth.local`, contact `albert@popcre.com`, admin
  - `95520c9b8c914cddb93d8d1bf65fa528@auth.local`, contact `nas-sync@popcre.com`, non-admin machine account
- NAS library ownership verified on 2026-06-09:
  - Character Licensed `177cf9de-3066-482e-956a-7ae8d8786c6d` owned by the SSO admin
  - Generic Decor `1b116ab7-d66b-4411-a691-21f34eadb731` owned by the SSO admin
- Both NAS libraries currently have internal public read-only rows in `seafile_db.InnerPubRepo`.
- The VPS stack is up; `nas-settings` is running and receiving NAS heartbeats.

## Partially done and exact current state

- The `nas-settings` web panel is live from `ghcr.io/u2giants/seafile:nas-settings-latest`.
- The latest `seaf-cli` image is published by CI, but the Synology containers still need a manual recreate.
- Current `nas-settings` status check on 2026-06-09 showed both library UUIDs reporting `daemon_alive=True` and `paused=False`, but `folder_size_cache` was not present in either payload.
- The NAS MCP/tool is not available in the current Codex tool list, and previous project docs state it is read-only for Docker. Do not rely on it for `docker pull` or `compose up`.

## Future plans discussed during the session

- Recreate the Synology containers so the NAS agent can enforce schedules and report cached folder sizes.
- Use the Seafile GUI to create/use an all-users group and share both NAS libraries read-write if every user should have write access.
- Onboard POP Creations users through Microsoft SSO.
- Optionally move the NAS compose/env files from `/tmp` to persistent NAS storage.

## Not started

- Synology-side recreate of `seaf-cli-char-licensed` and `seaf-cli-generic-decor`.
- Verification that cached folder-size data appears in the Libraries page.
- GUI read-write sharing for all users.
- Designer/staff onboarding.

## Decisions made and why

- Top-level `docs/` is now canonical because the task spec required `docs/architecture.md`, `docs/development.md`, `docs/configuration.md`, and `docs/deployment.md` roles exactly.
- `HANDOFF.md` remains present because work is still unfinished.
- Folder sizes are cached by the NAS agent, not calculated live in Seafile browsing, to avoid expensive recursive tree walks during normal browsing.
- NAS deploy remains manual SSH operator work because CI only publishes images and the NAS MCP cannot perform state-changing Docker operations.

## Dead ends or abandoned approaches

- Do not try to deploy/recreate NAS containers through GitHub Actions; CI must not SSH into production.
- Do not try to use the NAS MCP for Docker state changes; it is diagnostic/read-only for Docker according to current docs and unavailable in this session.
- Do not calculate recursive folder sizes live in Seahub's file browser.
- Do not rerun `seafile-server/CONFIGURE_OAUTH.sh`; it is an obsolete Google OAuth append script.

## Exact next action

Run this over SSH on `edgesynology1` as an operator with sufficient privileges:

```bash
DOCKER=/var/packages/ContainerManager/target/usr/bin/docker

# Rebuild /tmp/.env from a running container's env if needed; this avoids typing secrets.
sudo $DOCKER inspect seaf-cli-char-licensed \
  --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -E '^(SEAF_USERNAME|SEAF_PASSWORD|SEAF_STATUS_TOKEN)=' | sudo tee /tmp/.env >/dev/null

# If /tmp/seaf-cli-compose.yml is missing, stage this repo's
# synology-seaf-cli/docker-compose.yml to that path first.
sudo $DOCKER pull ghcr.io/u2giants/seafile:seaf-cli-latest
sudo $DOCKER compose -f /tmp/seaf-cli-compose.yml --env-file /tmp/.env up -d --force-recreate
```

Then verify:

```bash
sudo $DOCKER ps --filter name=seaf-cli
sudo $DOCKER logs --tail 80 seaf-cli-char-licensed
sudo $DOCKER logs --tail 80 seaf-cli-generic-decor
```

On the VPS, verify `folder_size_cache` appears after the containers report:

```bash
docker exec nas-settings sh -lc 'python - << "PY"
import json
from pathlib import Path
data=json.loads(Path("/data/status.json").read_text())
for uuid, entry in data.items():
    print(uuid, "folder_size_cache" in entry, entry.get("reported_at"))
PY'
```

In the GUI, visit `https://seafile.designflow.app/nas-settings/libraries`, click **Refresh sizes**, and confirm the cached folder-size table eventually populates.

## Known risks, blockers, or unknowns

- Remote SSH access path to `edgesynology1` is not documented in this repo. Ask Albert/operator if access is unavailable.
- `/tmp` on Synology is wiped on reboot. Recreate work may need `/tmp/seaf-cli-compose.yml` restaged from `synology-seaf-cli/docker-compose.yml`.
- Full recursive folder-size scans over multi-terabyte folders can take time and IO. They run in the background and are intentionally cached.
- The 2026-06-05 container removal root cause remains unknown.

## Session context that would otherwise be lost

- The user objected, correctly, that implementation phrases like `seafile_api.add_inner_pub_repo(repo_id, "r")` are not useful to a non-programmer. In plain English: that operation made the libraries visible to logged-in users as read-only.
- The user wants every user to have read-write permissions. The GUI path is: create/use a group for all users, then share each library to that group with Read-Write permission.
