# Synology seaf-cli — NAS Sync

Syncs folders from the NYC Synology NAS to Seafile Pro at `seafile.designflow.app`. The current NAS deployment is one Docker container that syncs multiple libraries.

**This is the NAS deployment.** An alternative Windows workstation deployment exists at `windows-workstation/` for running the same containers on a LAN-connected Windows machine via SMB mounts, offloading CPU from the NAS. Only one deployment should be active at a time.

**Status: the `seaf-cli` container lives on edgesynology1 and is managed over SSH from the VPS with `ssh edge1`.**

## Live Container

| Container | NAS path | Container path | Seafile library | UUID |
|-----------|----------|----------------|-----------------|------|
| `seaf-cli` | `/volume1/mac/Decor/Character Licensed` | `/library/char` | Character Licensed | `177cf9de-3066-482e-956a-7ae8d8786c6d` |
| `seaf-cli` | `/volume1/mac/Decor/Generic Decor` | `/library/decor` | Generic Decor | `1b116ab7-d66b-4411-a691-21f34eadb731` |
| `seaf-cli` | `/volume1/styleguides` | `/library/guides` | Styleguides | `b6e1d4c9-434e-4d8a-bde2-7f19be9c0838` |
| `seaf-cli` | `/volume1/mac/Art Library` | `/library/art` | ArtLibrary | `d28d5118-e991-431a-be3d-2e6a15246479` |

## Image

`ghcr.io/u2giants/seafile:seaf-cli-latest` — a wrapper built on `flrnnc/seafile-client` from `synology-seaf-cli/Dockerfile` in this repo. Built automatically by GitHub Actions on every commit to `synology-seaf-cli/Dockerfile`, `entrypoint.py`, or `seaf-entrypoint.py`.

Do not use `flrnnc/seafile-client:latest` directly — see Process Supervision below.

## How it works

The container runs `entrypoint.py` directly under `tini`:

- Starts `seaf-daemon` and registers `/library` as the sync path
- Discovers each `SEAF_LIBRARY_<KEY>` variable and syncs that UUID to `/library/<key>`
- Writes `.seafile-ignore` into each library path if missing so Synology metadata and common temp files are ignored
- Clears stale failed clone tasks for a repo before retrying `seaf-cli sync`
- Syncs the mounted folders to the Seafile server continuously
- Reports status every 30 seconds, executes queued panel commands, and applies the current weekday/weekend schedule by toggling per-repo `auto-sync`
- Rebuilds cached recursive source-folder sizes nightly after 2 AM New York time, or immediately when the panel queues `refresh_folder_sizes`
- Watchdog loop: polls `seaf-daemon`'s PID every 10 seconds; calls `sys.exit(1)` if it dies

```
/library/<key> (NAS bind mount, read-write)
    │
    ▼ entrypoint.py → seaf-daemon
    ▼
Seafile server → S3
```

## Process Supervision

The wrapper image uses `tini` as PID 1. Process tree inside each container:

```
tini (PID 1)
  └── python3 /home/seafile/entrypoint.py
        └── seaf-daemon
```

When seaf-daemon dies:
1. `entrypoint.py` watchdog detects it → `sys.exit(1)`
2. `tini` reaps any zombie processes
3. Docker `restart: unless-stopped` restarts the container

**Why this matters:** The upstream `flrnnc/seafile-client` image has three confirmed bugs that caused silent production failures before this wrapper was introduced:
- seaf-daemon death left a zombie process; container stayed "running" but synced nothing
- The process exited with code 0, preventing Docker's restart policy from firing
- The health check always reported healthy regardless of sync state

See `docs/architecture.md` → "Process Supervision" for the full explanation. The upstream issues have been reported at [gitlab.com/flrnnc-oss/docker-seafile-client](https://gitlab.com/flrnnc-oss/docker-seafile-client).

## Check sync status

From the VPS, SSH to the Synology and use Synology's full Docker path:

```bash
ssh edge1
DOCKER=/var/packages/ContainerManager/target/usr/bin/docker
sudo -n $DOCKER logs --tail 50 seaf-cli
```

**Healthy sync log pattern:**
```
Initializing `seaf-cli`.
Starting `seaf-cli`.
Library <name> is already synced.
Monitoring seaf-daemon (PID N)
```

**Unhealthy signs:**
- "seaf-daemon (PID N) has exited" followed by container restart — expected recovery behaviour
- Container repeatedly restarting with no "synchronized" in logs — check credentials or server reachability
- No logs at all — container stopped, Docker restart policy not firing

Health check status:
```bash
sudo -n $DOCKER inspect --format='{{.State.Health.Status}}' seaf-cli
```

## Schedule and library settings

The weekday/weekend sync schedule is configurable at:
```
https://seafile.designflow.app/sys/  → NAS Sync Settings (bottom of left nav)
```

Schedule changes are handed to the container on the next 30-second status heartbeat
and are enforced by toggling the synced repo's `auto-sync` property. Weekday and
weekend windows are separate; an end time earlier than the start time means the
window runs overnight.

On first sync registration, the wrapper writes `.seafile-ignore` into each library
path if the file is missing. That ignore file includes Synology metadata directories
such as `@eaDir` plus common temporary files.

## Failed initial clone recovery

### 2026-06-11 Character Licensed too-many-files failure

What changed:
The live Seafile fileserver config was raised to `max_sync_file_count = 5000000`
with `fs_id_list_request_timeout = 600`, and commit `b3436f7` added wrapper cleanup
for failed clone tasks before retrying `seaf-cli sync`.

Why:
The Character Licensed library exceeded Seafile's default file-count limit. After
the server-side limit was fixed, seaf-daemon still kept a failed clone task in
`/seafile/seafile-data/clone.db`, causing retry attempts to report "Task is already
in progress".

Future sessions should:
Do not delete `seaf-cli-data` for this symptom. Use the current image; it backs up
`clone.db` and deletes only rows for the affected repo when the existing clone task
is already in `state=error`. Active fetch/upload clone tasks are intentionally not
cleared.

## Updating the image

To release a runtime change to `Dockerfile` or `entrypoint.py`:

1. Commit to `main` — GitHub Actions builds and pushes two tags: `ghcr.io/u2giants/seafile:seaf-cli-latest` (mutable pointer) and `ghcr.io/u2giants/seafile:sha-<commit>` (immutable, for audit + rollback)
2. Wait for CI to pass: https://github.com/u2giants/seafile/actions
3. Pull + recreate the container on edgesynology1.

> **Important:** do the recreate over SSH from the VPS with `ssh edge1`. Docker's full path is `/var/packages/ContainerManager/target/usr/bin/docker`, and `/tmp` is wiped on reboot so the compose + `.env` usually need re-staging first.

Self-contained recreate block (paste over SSH on **edgesynology1**; reads creds from the running container, so no secrets are typed). Stage the current `synology-seaf-cli/docker-compose.yml` as `/tmp/seaf-cli-compose-codex.yml` first and verify the service list is only `seaf-cli`:

```bash
DOCKER=/var/packages/ContainerManager/target/usr/bin/docker
# Rebuild /tmp/.env from the running container's baked-in credentials (nothing typed)
sudo -n $DOCKER inspect seaf-cli \
  --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -E '^(SEAF_USERNAME|SEAF_PASSWORD|SEAF_STATUS_TOKEN)=' | sudo -n tee /tmp/.env >/dev/null
sudo -n $DOCKER compose -f /tmp/seaf-cli-compose-codex.yml --env-file /tmp/.env config --services
sudo -n $DOCKER pull ghcr.io/u2giants/seafile:seaf-cli-latest
sudo -n $DOCKER compose -f /tmp/seaf-cli-compose-codex.yml --env-file /tmp/.env up -d
```

If Compose reports that `/seaf-cli` already exists, remove only that container and rerun `up -d`; the `seaf-cli-data` volume preserves sync state:

```bash
sudo -n $DOCKER rm -f seaf-cli
sudo -n $DOCKER compose -f /tmp/seaf-cli-compose-codex.yml --env-file /tmp/.env up -d
```

`docker-compose.yml` changes (environment, volumes) only need the compose-up step — no image rebuild required.

### Rollback

To roll back, pin the affected service's `image:` in the compose file to a known-good immutable tag and `up -d` — never rebuild on the NAS or hand-edit container state:

```yaml
image: ghcr.io/u2giants/seafile:sha-<older-commit>
```

Find prior tags under the repo's GHCR package or in the GitHub Actions run history (each run's commit SHA is the `sha-` tag it published).

## Re-deploy after container removal

The container has `restart: unless-stopped` — it survives reboots without needing the compose file on disk.

If a container is manually removed:
1. Write the compose file from this repo to `/tmp/seaf-cli-compose-codex.yml` on edgesynology1
2. Write `/tmp/.env` with `SEAF_USERNAME` and `SEAF_PASSWORD` (see `/opt/seafile/CREDENTIALS.txt` on VPS)
3. Pull the image and start:
```bash
DOCKER=/var/packages/ContainerManager/target/usr/bin/docker
sudo -n $DOCKER pull ghcr.io/u2giants/seafile:seaf-cli-latest
sudo -n $DOCKER compose -f /tmp/seaf-cli-compose-codex.yml --env-file /tmp/.env up -d
```

Note: Docker on Synology is at `/var/packages/ContainerManager/target/usr/bin/docker` — not in PATH.

## Volume notes

- `seaf-cli-data` volume (`/seafile`) — seaf-daemon state, sync metadata, failed-clone database, and cached folder-size data. Deleting forces a full re-sync on next start.
- `/library/<key>` paths are live NAS bind mounts, not disposable staging volumes.

## Tests

`test_entrypoint.py` stubs the Seafile RPC module and verifies command dispatch,
schedule enforcement, cached folder-size calculations, credential redaction, and
failed-clone cleanup:

```bash
python3 synology-seaf-cli/test_entrypoint.py
```

## Connection details

| | |
|---|---|
| Seafile server | https://seafile.designflow.app |
| Sync account | nas-sync@popcre.com |
| Password | `/opt/seafile/CREDENTIALS.txt` on VPS |
