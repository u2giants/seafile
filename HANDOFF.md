# HANDOFF

Last updated: 2026-06-05. Delete this file once NAS sync is restored **and** the 8 designers are onboarded.

A new developer/AI should read `AGENTS.md` first, then this file for live state.

---

## What this session did (2026-06-05)

1. **Fixed seaf-cli staging resource usage** (`synology-seaf-cli/seaf-entrypoint.py`, commit `5274587`):
   - `/library` is now populated with **hardlinks** (`os.link`) instead of `shutil.copy2`, so the in-window working set is no longer physically duplicated on the NAS. Falls back to copy only if `/source` and `/library` are on different filesystems.
   - File selection is a single `os.scandir` pass (mtime from the dir entry) instead of `os.walk` + a `stat()` per file — ~half the metadata I/O on the hourly refresh of the ~467k-file Character Licensed tree.
   - Validated with a local 15-check harness (date filter, hardlink creation, idempotent rerun, aged-out removal, in-place replace → relink, copy fallback). All passed.
2. **Brought CI in line with the org CI/CD rules** (`.github/workflows/seaf-cli-image.yml`, commits `1c9fd18`, `546e0d4`, `84fa5d6`):
   - Publishes an immutable `sha-<commit>` tag alongside `seaf-cli-latest` (audit + rollback).
   - Added `concurrency: cancel-in-progress`, gha Docker layer cache, and `setup-buildx-action` (required for the gha cache export — the first attempt failed without it).
   - Bumped all actions to Node 24 majors (checkout v6, setup-python v6, buildx v4, login v4, build-push v7).
3. **Documentation** (this session): rewrote the stale parts of `AGENTS.md`, `README.md`, `CLAUDE.md`, `synology-seaf-cli/README.md`, and two spots in `seafile-server/docs/`. Documented the no-deployment-platform model as a §25 exception. Recorded the container-removal incident.

All of the above is committed and pushed to `main`. CI is green; the current code is published as `ghcr.io/u2giants/seafile:sha-84fa5d6...` and `:seaf-cli-latest`.

---

## Current live state

- **NAS sync is DOWN.** Both `seaf-cli-char-licensed` and `seaf-cli-generic-decor` have been **removed** from edgesynology1 (not stopped — `docker ps -a` lists neither). This was discovered this session; the cause is unknown (no docker events in the last 72h). New/changed design files are NOT being pushed to Seafile right now.
- **No data lost.** The Seafile libraries, their S3 data, and the Docker volumes (`seaf-cli-*-data`, `seaf-cli-*-staging`) are intact. The `seaf-cli-latest` image is still on the NAS. Re-deploying will not trigger a full re-hash/re-upload.
- **VPS Seafile server is up** at `https://seafile.designflow.app` (Seafile Pro `13.0-latest`, plus MariaDB, Redis, Caddy, nas-settings).

---

## What is NOT done

1. **Restore NAS sync (or cut over to Windows)** — not started. The new hardlink/scandir image is built and waiting; nothing runs it until containers are re-deployed.
2. **Onboard 8 São Paulo designers** — not started. System is ready (M365 SSO auto-creates accounts); they just need the link and library shares.
3. **Windows workstation cutover** — optional alternative to #1; scripts are ready but never run (needs Docker Desktop confirmed on the Windows machine).

---

## Exact next action

Decide between restoring on the NAS vs. the Windows cutover, then:

**To restore on the NAS** (fastest path back to working sync):
1. Investigate why the containers vanished — check Synology Container Manager / Package Center logs and recent NAS reboots/upgrades. (Optional but recommended so it doesn't recur.)
2. Re-write `synology-seaf-cli/docker-compose.yml` to `/tmp/seaf-cli-compose.yml` on edgesynology1 and `/tmp/.env` with `NAS_SYNC_PASSWORD` (from `/opt/seafile/CREDENTIALS.txt`). Use the NAS MCP base64+tee pattern (see AGENTS.md).
3. `docker compose -f /tmp/seaf-cli-compose.yml --env-file /tmp/.env up -d` (base64-encoded via NAS MCP; docker is at `/var/packages/ContainerManager/target/usr/bin/docker`).
4. Verify both containers report healthy and logs show "synchronized".

**To onboard designers** (independent of the above):
- Send `https://seafile.designflow.app`; each signs in with their POP Creations M365 account; then share Character Licensed + Generic Decor with each at Read/Write.

---

## Decisions made this session, and why

- **Hardlinks over copies for staging** — eliminates a second physical copy of the working set; seaf-cli only reads `/library`, so a shared inode is safe. Copy fallback preserves correctness on cross-filesystem setups.
- **`main` only, no branches, no PRs** — Albert confirmed this repo's workflow. (An earlier branch+PR this session was reverted and the work moved to `main`.)
- **§25 CI/CD exception** — there is no deployment platform (Synology NAS + direct-Docker VPS), so CI builds/publishes only and deployment stays a manual repo-driven pull. CI must never SSH into production.
- **Kept `FROM flrnnc/seafile-client:latest` unpinned** — community fixes flow in automatically; full reproducibility (digest pin) is logged as optional Pending Work.

## Known risks / unknowns

- **Root cause of the container removal is unknown.** If it recurs after re-deploy, the `restart: unless-stopped` policy is not enough; investigate Container Manager behavior on NAS reboot/upgrade.
- **seaf-cli is 7.0.10** (old, from the community base) against a 13.0 server. Works today via protocol back-compat; no newer community image exists. Not a blocker.
