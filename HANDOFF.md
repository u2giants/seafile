# HANDOFF

## What this is

This session diagnosed and fixed critical process management bugs in the Synology NAS seaf-cli containers, built a proper wrapper Docker image, set up a CI/CD pipeline, and updated all documentation. One action remains before the fix is live in production.

## What is fully done

- **Root cause analysis** — Three upstream bugs in `flrnnc/seafile-client` confirmed in the live containers:
  1. `healthcheck()` always exits 0 (missing `return` statement)
  2. seaf-daemon becomes a zombie with no detection or restart (`follow()` blocked on `tail`, exited code 0)
  3. `chown -R` on every container start (in `entrypoint-docker.sh`, though this was bypassed by the existing compose override)
  - One additional bug in our own `seaf-entrypoint.py`: `os.execv` killed the hourly refresh thread

- **Wrapper image built and published** — `ghcr.io/u2giants/seafile:seaf-cli-latest` is live at GHCR, built from `synology-seaf-cli/` in this repo. Includes:
  - `tini` as PID 1 (zombie reaping, signal forwarding)
  - Fixed `entrypoint.py` (watchdog loop, correct healthcheck exit codes, SIGTERM handler, timeouts, no shell injection, credentials redacted from debug logs)
  - Fixed `seaf-entrypoint.py` (`subprocess.run` instead of `os.execv` so the hourly refresh thread survives)

- **GitHub Actions workflow** — `.github/workflows/seaf-cli-image.yml` — triggers on changes to `synology-seaf-cli/Dockerfile`, `entrypoint.py`, or `seaf-entrypoint.py`; runs pyflakes lint then builds and pushes to GHCR

- **`docker-compose.yml` updated** — image changed from `flrnnc/seafile-client:latest` to `ghcr.io/u2giants/seafile:seaf-cli-latest`; inline entrypoint download removed (baked into image now)

- **AGENTS.md updated** — idiosyncratic decisions, deployment section, repo structure

- **All documentation updated** — README.md, architecture.md, synology-seaf-cli/README.md, deployment.md, development.md

- **Upstream issues prepared** — three ready-to-paste GitLab issue files in `/home/ai/seafile-client-fix/` on the VPS

## What is NOT done yet — must be done before the fix is live

### 1. NAS containers must be restarted with the new image (CRITICAL)

The new `docker-compose.yml` is committed and the image is published, but the containers on edgesynology1 are still running the OLD configuration (`flrnnc/seafile-client` with the inline entrypoint download). All the bugs are still present in the live containers until this step is done.

The exact steps via NAS MCP (target: edgesynology1):

**Step A — write the updated compose file to /tmp:**
Use NAS MCP `run_command` with base64-encoded tee command to write the current `synology-seaf-cli/docker-compose.yml` from this repo to `/tmp/seaf-cli-compose.yml` on the NAS. (The compose file is at `https://raw.githubusercontent.com/u2giants/seafile/main/synology-seaf-cli/docker-compose.yml`)

**Step B — pull the new image:**
```bash
CMD="/var/packages/ContainerManager/target/usr/bin/docker pull ghcr.io/u2giants/seafile:seaf-cli-latest"
```

**Step C — recreate both containers:**
```bash
CMD="/var/packages/ContainerManager/target/usr/bin/docker compose -f /tmp/seaf-cli-compose.yml --env-file /tmp/.env up -d --force-recreate"
```
(Ensure `/tmp/.env` exists with `SEAF_USERNAME` and `SEAF_PASSWORD` — credentials in `/opt/seafile/CREDENTIALS.txt` on VPS)

**Step D — verify:**
Check `docker top seaf-cli-char-licensed` shows `tini → seaf-entrypoint.py → entrypoint.py → seaf-daemon`. Check `docker inspect --format='{{.State.Health.Status}}' seaf-cli-char-licensed` shows `healthy`.

### 2. File the three GitLab upstream issues

Three issue bodies are ready at `/home/ai/seafile-client-fix/` on the VPS:
- `issue-1-healthcheck-always-zero.md` — **file first, most critical**
- `issue-2-zombie-daemon-no-watchdog.md`
- `issue-3-chown-r-on-every-start.md`

Go to https://gitlab.com/flrnnc-oss/docker-seafile-client/-/issues/new. Use the first `#` heading as the title; paste the file body. Requires a GitLab account — no automation available (no `glab` CLI, no GitLab token on this VPS).

### 3. Designer onboarding (pre-existing, unrelated to this session)

8 São Paulo designers still need library access. Send them `https://seafile.designflow.app`; they sign in with M365 SSO; then Albert shares Character Licensed and Generic Decor libraries via the web UI (Read/Write). See `seafile-server/docs/development.md` → "Managing Users".

## Decisions made this session and why

- **Wrapper image over full fork** — upstream bugs are real but the maintainer is active (379 commits, 17 releases). Wrapper lets us fix production now while leaving door open for upstream fixes to land.
- **`subprocess.run` over `os.execv`** — preserves the hourly refresh thread that `os.execv` was silently killing. This was a pre-existing bug in our own `seaf-entrypoint.py`.
- **`sys.exit(result.returncode)` not `sys.exit(1)` from seaf-entrypoint.py** — `restart: unless-stopped` restarts on any exit including 0, so the exit code doesn't matter for restart behavior.
- **Single atomic git commit for all code + docs** — avoids a state where compose references an image that hasn't built yet.
- **GitHub `workflow` scope added separately** — the initial commit token lacked the `workflow` OAuth scope needed to push to `.github/workflows/`. Required `gh auth refresh -s workflow` using device code flow (browser auth from another machine).

## Dead ends / approaches abandoned

- **Direct `gh auth refresh`** — requires a browser or interactive TTY; the VPS is headless. Solved with device code flow (`--hostname github.com` flag required).
- **Git tree API with `.github/workflows/` path** — returned HTTP 404 regardless of parameters; root cause was missing `workflow` OAuth scope on the token. Misleading error message.
- **Single commit including the workflow file** — blocked by the above; split into two commits.

## Known risks

- The `seaf-cli-*-data` volumes have accumulated sync state from the buggy containers. After restart with the new image, seaf-daemon will resume from its last sync state — this is correct behavior. If any corruption occurred while the zombie was running, a full re-sync can be forced by deleting the `*-data` volumes (seaf-daemon re-initializes from scratch).
- The GHCR image is public (repo is public). This is intentional and safe — the image contains no secrets.

## Context that would otherwise be lost

- The `seaf-entrypoint.py` `os.execv` bug was not in the upstream `flrnnc/seafile-client` — it was in our own wrapper script. The upstream bugs are in `entrypoint.py` (the upstream file). Our `seaf-entrypoint.py` had a separate silent bug where the hourly refresh never actually ran because exec replaced the process before the first `time.sleep(3600)` completed.
- The containers were never using `/entrypoint.sh` (the shell wrapper that does `chown -R`). The original compose file had an inline entrypoint override that bypassed it. So the `chown -R` observed at 10-22% CPU was likely from a period before the entrypoint override was added, or from a different container configuration. The wrapper image makes this permanently irrelevant.
- The `SEAF_SETTINGS_URL` env var points to the nas-settings panel API. If the VPS is down, seaf-entrypoint.py falls back silently to `SEAF_INGEST_DAYS` from the compose env. No manual intervention needed.
