# Synology seaf-cli — NAS Sync

Syncs folders from the NYC Synology NAS to Seafile Pro at `seafile.designflow.app`. One Docker container per library.

**This is the NAS deployment.** An alternative Windows workstation deployment exists at `windows-workstation/` for running the same containers on a LAN-connected Windows machine via SMB mounts, offloading CPU from the NAS. Only one deployment should be active at a time.

**Status: Both containers live on edgesynology1.**

## Live Containers

| Container | NAS path (→ /source) | Seafile library | UUID |
|-----------|----------------------|-----------------|------|
| `seaf-cli-char-licensed` | `/volume1/mac/Decor/Character Licensed` | Character Licensed | `177cf9de-3066-482e-956a-7ae8d8786c6d` |
| `seaf-cli-generic-decor` | `/volume1/mac/Decor/Generic Decor` | Generic Decor | `1b116ab7-d66b-4411-a691-21f34eadb731` |

## Image

`ghcr.io/u2giants/seafile:seaf-cli-latest` — a wrapper built on `flrnnc/seafile-client` from `synology-seaf-cli/Dockerfile` in this repo. Built automatically by GitHub Actions on every commit to `synology-seaf-cli/Dockerfile`, `entrypoint.py`, or `seaf-entrypoint.py`.

Do not use `flrnnc/seafile-client:latest` directly — see Process Supervision below.

## How it works

Each container runs a two-stage entrypoint:

**Stage 1 — `seaf-entrypoint.py`** (baked into the wrapper image at `/home/seafile/seaf-entrypoint.py`):
- Filters files from `/source` by mtime (`SEAF_INGEST_DAYS`) using a single `os.scandir` pass (mtime read from the directory entry — no extra `stat()` per file)
- Hardlinks qualifying files into `/library` (staging volume), falling back to a copy only if `/source` and `/library` are on different filesystems; removes stale ones. Hardlinks share the source inode, so the working set is not physically duplicated on the NAS
- Fetches per-library `ingest_days` from the nas-settings API; falls back to `SEAF_INGEST_DAYS` env var on failure
- Starts a daemon thread that re-runs the above every hour
- Launches Stage 2 via `subprocess.run` (not `os.execv` — see Process Supervision)

**Stage 2 — `entrypoint.py`** (baked into the wrapper image at `/home/seafile/entrypoint.py`):
- Starts `seaf-daemon` and registers `/library` as the sync path
- Syncs `/library` to the Seafile server continuously
- Watchdog loop: polls `seaf-daemon`'s PID every 10 seconds; calls `sys.exit(1)` if it dies

```
/source (NAS bind mount, read-only)
    │
    ▼ seaf-entrypoint.py
    ▼
/library (Docker staging volume)
    │
    ▼ entrypoint.py → seaf-daemon
    ▼
Seafile server → S3
```

## Process Supervision

The wrapper image uses `tini` as PID 1. Process tree inside each container:

```
tini (PID 1)
  └── seaf-entrypoint.py
        ├── refresh_loop thread (hourly)
        └── entrypoint.py [subprocess]
              └── seaf-daemon
```

When seaf-daemon dies:
1. `entrypoint.py` watchdog detects it → `sys.exit(1)`
2. `seaf-entrypoint.py` subprocess returns → `sys.exit(1)`
3. `tini` reaps any zombie processes
4. Docker `restart: unless-stopped` restarts the container

**Why this matters:** The upstream `flrnnc/seafile-client` image has three confirmed bugs that caused silent production failures before this wrapper was introduced:
- seaf-daemon death left a zombie process; container stayed "running" but synced nothing
- The process exited with code 0, preventing Docker's restart policy from firing
- The health check always reported healthy regardless of sync state

See `seafile-server/docs/architecture.md` → "Process Supervision" for the full explanation. The upstream issues have been reported at [gitlab.com/flrnnc-oss/docker-seafile-client](https://gitlab.com/flrnnc-oss/docker-seafile-client).

## Check sync status

Via NAS MCP `run_command` (target: edgesynology1). All docker commands must be base64-encoded because the MCP blocks the string "docker":

```bash
# docker logs --tail 50 seaf-cli-char-licensed
CMD="docker logs --tail 50 seaf-cli-char-licensed"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'
```

**Healthy sync log pattern:**
```
seaf-entrypoint  Ingest window: 730 days — N qualifying files
seaf-entrypoint  Library ready — N files updated
[upstream]       seafile-data dir … started
[upstream]       Monitoring seaf-daemon (PID N)
[upstream]       synchronized
```

**Unhealthy signs:**
- "seaf-daemon (PID N) has exited" followed by container restart — expected recovery behaviour
- Container repeatedly restarting with no "synchronized" in logs — check credentials or server reachability
- No logs at all — container stopped, Docker restart policy not firing

Health check status:
```bash
# docker inspect --format='{{.State.Health.Status}}' seaf-cli-char-licensed
CMD="docker inspect --format='{{.State.Health.Status}}' seaf-cli-char-licensed"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'
```

## Ingest window settings

The per-library ingest window (how far back files are synced) is configurable at:
```
https://seafile.designflow.app/sys/  → NAS Sync Settings (bottom of left nav)
```

Changes take effect on the next hourly refresh, or immediately if the container is restarted.

## Updating the image

To release a change to `Dockerfile`, `entrypoint.py`, or `seaf-entrypoint.py`:

1. Commit to `main` — GitHub Actions builds and pushes two tags: `ghcr.io/u2giants/seafile:seaf-cli-latest` (mutable pointer) and `ghcr.io/u2giants/seafile:sha-<commit>` (immutable, for audit + rollback)
2. Wait for CI to pass: https://github.com/u2giants/seafile/actions
3. Pull the new image on edgesynology1 and recreate containers via NAS MCP:

```bash
# docker pull ghcr.io/u2giants/seafile:seaf-cli-latest
CMD="docker pull ghcr.io/u2giants/seafile:seaf-cli-latest"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'

# docker compose -f /tmp/seaf-cli-compose.yml up -d --force-recreate
CMD="docker compose -f /tmp/seaf-cli-compose.yml up -d --force-recreate"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'
```

`docker-compose.yml` changes (environment, volumes) only need step 3 — no image rebuild required. Write the updated compose file to `/tmp/seaf-cli-compose.yml` on the NAS first.

### Rollback

To roll back, pin the affected service's `image:` in the compose file to a known-good immutable tag and `up -d` — never rebuild on the NAS or hand-edit container state:

```yaml
image: ghcr.io/u2giants/seafile:sha-<older-commit>
```

Find prior tags under the repo's GHCR package or in the GitHub Actions run history (each run's commit SHA is the `sha-` tag it published).

## Re-deploy after container removal

Containers have `restart: unless-stopped` — they survive reboots without needing the compose file on disk.

If a container is manually removed:
1. Write the compose file from this repo to `/tmp/seaf-cli-compose.yml` on edgesynology1 (via NAS MCP base64+tee)
2. Write `/tmp/.env` with `SEAF_USERNAME` and `SEAF_PASSWORD` (see `/opt/seafile/CREDENTIALS.txt` on VPS)
3. Pull the image and start:
```bash
CMD="/var/packages/ContainerManager/target/usr/bin/docker compose -f /tmp/seaf-cli-compose.yml --env-file /tmp/.env up -d"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'
```

Note: Docker on Synology is at `/var/packages/ContainerManager/target/usr/bin/docker` — not in PATH.

## Volume notes

- `seaf-cli-*-data` volumes (`/seafile`) — seaf-daemon state and sync metadata. Deleting forces a full re-sync on next start.
- `seaf-cli-*-staging` volumes (`/library`) — date-filtered file snapshot. Safe to delete; repopulated by `seaf-entrypoint.py` on next start.

## Connection details

| | |
|---|---|
| Seafile server | https://seafile.designflow.app |
| Sync account | nas-sync@popcre.com |
| Password | `/opt/seafile/CREDENTIALS.txt` on VPS |
