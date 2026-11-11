---
summary: Intentional quirks and do-not-change notes: DNS-only record, wrapper image, live /library bind mounts, schedule windows, polling panel, docker-socket grant.
kind: living
status: current
read-when: something looks wrong or misconfigured and you are about to change it
---

Intentional quirks and non-obvious decisions, moved out of AGENTS.md on 2026-11-11 (documentation overhaul, popcre/designflow-backend issue 391). Each entry explains what it looks like, what is actually true, why, and why not to change it.


### Cloudflare proxy disabled

Looks like:
The public host should be behind Cloudflare orange-cloud proxy.

Actually:
`seafile.designflow.app` is DNS-only.

Why:
Seafile desktop sync can use protocols/paths that do not work reliably through Cloudflare's HTTP proxy layer.

Do not change because:
Proxying the record can break desktop sync clients.

### seaf-cli wrapper image

Looks like:
`ghcr.io/u2giants/seafile:seaf-cli-latest` is an unnecessary wrapper around `flrnnc/seafile-client`.

Actually:
The wrapper adds `tini`, fixed process supervision, a correct healthcheck, stale PID/socket cleanup, status reporting, command dispatch, schedule enforcement, and cached folder-size scanning.

Why:
The upstream community image has caused silent sync failures and does not provide this deployment's admin bridge.

Do not change because:
Using the upstream image directly removes production safeguards and the NAS Settings control loop.

### NAS `/library/<key>` paths are live bind mounts

Looks like:
`/library` is a disposable staging volume from the older wrapper design.

Actually:
The current NAS compose bind-mounts live NAS folders directly under `/library/<key>` in the single `seaf-cli` container. The named `seaf-cli-data` volume is only for seaf-daemon state and caches.

Why:
The current wrapper supports multi-library sync directly through `SEAF_LIBRARY_<KEY>` variables and Seafile's exact `seafile-ignore.txt` filename.

Do not change because:
Deleting `/library` paths or treating them as cache can affect live NAS data. To force sync-state rebuilds, operate on `seaf-cli-data` only after an explicit rollback/recovery plan.

### Sync schedule has weekday and weekend windows

Looks like:
The schedule is a single days/start/end block.

Actually:
The panel writes a schedule with separate `weekdays` and `weekends` windows, a shared timezone, and an outer `enabled` flag. The NAS agent still accepts the older one-window shape for backward compatibility.

Why:
Business-hour and off-hour sync needs differ between weekdays and weekends, and overnight windows are common.

Do not change because:
Collapsing the shape back to one window removes the requested granularity and can make existing settings ambiguous.

### `nas-settings` cannot push commands to the NAS

Looks like:
The VPS panel should directly call the NAS.

Actually:
The NAS containers poll `/api/status` every 30 seconds and receive queued commands in the response.

Why:
The VPS cannot reliably reach the NAS, and commands need to route by library UUID rather than ephemeral container hostnames.

Do not change because:
Direct push assumptions break remote operation; hostname-keyed commands can miss the target container.

### `/api/settings` is unauthenticated

Looks like:
The endpoint is missing auth.

Actually:
It intentionally exposes only non-secret library UUID/settings data so NAS containers can poll without a Seafile admin session.

Why:
The NAS agent needs ingest/schedule settings before it can report authenticated status; write/admin endpoints remain protected.

Do not change because:
Adding browser-session auth would break the NAS agent's hourly settings refresh.

### NAS deploy uses SSH from the VPS

Looks like:
GitHub Actions or the NAS MCP should recreate containers after image publish, or the old per-library container names should be managed directly.

Actually:
CI only publishes images. From the VPS, `ssh edge1` logs in to `edgesynology1` as `ai`, but the `ai` account has NO passwordless sudo (the old docker sudoers drop-in was wiped by a DSM update). Owner ruling 2026-10-26 (verbatim: "i'm not going to restore AI admin access on the NAS"): AI admin access on the NAS will NOT be restored; do not ask again. NAS-side Docker operations (compose pull/up) are run by the owner when requested; stage the file changes first (the `ai` account owns `/volume1/docker/seaf-cli/`), then hand the owner the exact command. Routine updates still deploy themselves via Watchtower; the panel's memory-limit control needs no NAS access at runtime. The live NAS deployment is the single `seaf-cli` container from `synology-seaf-cli/docker-compose.yml`.

Why:
There is no deploy platform. The `ai` account has a narrow sudoers drop-in for the Synology Docker binary, and old staged files such as `/tmp/seaf-cli-compose.yml` may still describe obsolete per-library containers.

Do not change because:
Using stale two-service compose files or old container names can recreate the wrong topology. Stage the current compose file and verify `docker compose config --services` shows only `seaf-cli` before running `up`.

### Verify the live VPS before deploying

What changed:
On 2026-06-16, a deployment attempt first landed on the wrong host (`root@hetz`; historical private address in the protected recovery reference) where `/worksp/seafile` was a stale repo clone and no Seafile containers existed.

Why:
The live public host resolves to `172.233.14.233` and should identify as `seafile-br`; `/opt/seafile` holds the runtime `.env` and base compose files, while `nas-settings.yml` is deployed from `/home/ai/seafile-repo/seafile-server/nas-settings.yml`.

Future sessions should:
Before running Docker deploy commands, confirm `hostname`, `ls -la /opt/seafile`, and `docker ps` show `seafile`, `seafile-caddy`, and `nas-settings`. If those are absent, stop and find the live VPS instead of adapting commands to the wrong machine.

### seaf-cli failed clone tasks self-heal

What changed:
On 2026-06-11, Character Licensed hit Seafile's "too many files" sync limit and left a failed clone task in `/seafile/seafile-data/clone.db`. Commit `b3436f7` added wrapper cleanup for failed clone tasks before retrying `seaf-cli sync`.

Why:
After the server-side limit was raised, seaf-daemon still returned "Task is already in progress" for the stale failed clone task.

Future sessions should:
Do not delete the `seaf-cli-data` volume for this failure mode. Confirm the server has the intended fileserver limits, then let the current image clear only `state=error` clone rows for the affected repo; active fetch/upload tasks are intentionally left alone.

### 2026-06-19 Generic Decor false-synchronized state

What changed:
Generic Decor drift was traced to Synology host inotify exhaustion, not a stale Seafile index. `seaf-daemon` logged `fail to add watch` / `No space left on device` while the host limit was still `fs.inotify.max_user_watches=8192`; the synced trees contain roughly 541k directories, about 82% of them `@eaDir` thumbnail/metadata junk.

Why:
When directories are not watched, NAS edits there do not fire events, so `seaf-cli status` can report `synchronized` because the client index sees no change. Restarting `seaf-daemon` runs a one-time scan and can temporarily mask the symptom while leaving the inotify limit broken.

Future sessions should:
Do not treat restart as the repair. Raise the Synology host inotify limits persistently via a DSM boot-up task, then deploy the updated `synology-seaf-cli` image. Seafile ignore files must be named exactly `seafile-ignore.txt`; `.seafile-ignore` is not recognized. Ignore rules are cleanup/hygiene and may not reduce inotify watches.

### seaf-cli "bugs" reported against this image are usually base-image bugs, already fixed here

What changed:
A 2026-06 review reported three seaf-cli container bugs — `healthcheck()` always exits 0 (no return), `seaf-daemon` zombie / `tail -f` parking with no restart and no tini, and an unconditional `chown -R seafile:seafile /seafile /library`. Verified against source: all three live in the upstream base image `flrnnc/seafile-client` (its `/entrypoint.sh` and `/home/seafile/entrypoint.py`), NOT in upstream Seafile's `seaf-cli`/`seaf-daemon`, and NOT in this wrapper.

Why:
This image's `Dockerfile` overrides `ENTRYPOINT` to `tini -- /home/seafile/entrypoint.py` (our own `synology-seaf-cli/entrypoint.py`), bypassing the base `/entrypoint.sh` entirely. Our entrypoint already fixes/bypasses all three: `healthcheck()` returns `0/1` and guards a missing rpc socket; `watch()` polls the daemon PID and exits non-zero so Docker restarts it; SIGTERM/SIGINT call `seaf-cli stop`; tini is PID 1; and no `chown -R` runs (no base shell wrapper executes).

Future sessions should:
Do not re-fix those three — they are not present in the running image. Verify against `synology-seaf-cli/entrypoint.py` + `Dockerfile`, not against the `flrnnc/seafile-client` base. The only genuine wrapper bug from that review was the ignore filename/timing (`.seafile-ignore`, written only on first clone), fixed in 8e0f3c8. The real upstream-Seafile defect is separate and unfixed: the worktree monitor (`wt-monitor-linux.c`) adds inotify watches to ignored directories too, so `seafile-ignore.txt` does not reduce inotify watch count.

### seaf-cli deploys ONLY from /volume1/docker/seaf-cli with a .env (2026-06-21 incident)

What changed:
The seaf-cli stack is canonically deployed at `/volume1/docker/seaf-cli/` on edgesynology1 — `docker-compose.yml` (from `synology-seaf-cli/`) + a `.env` (chmod 600) loaded via `env_file:`. It is in Watchtower's watch list (`synology-monitor` `deploy/synology/docker-compose.agent.yml`).

Why:
It had drifted to a personal home dir with creds in a non-auto-loaded `seaf-cli.env`. `sudo docker compose up -d` (no `--env-file`) recreated the container with an empty env — `sudo` strips exported shell vars — so it started with no login (`Bad configuration: SEAF_USERNAME required`) and crash-looped. It was also outside Watchtower's scope, so image fixes never auto-deployed.

Future sessions should:
Never deploy seaf-cli from a home dir or `/tmp`, and never pass creds via shell env + `sudo`. Use the `.env` in the stack dir (`env_file:` fails loud if missing). Keep `seaf-cli` in Watchtower's command list. The repo compose is the source of truth — copy it as-is; do not hand-maintain `-codex`/`-tmp` variants. Full detail in `synology-seaf-cli/README.md` → "2026-06-21 incident".

### Seahub template overrides are full-file copies

Looks like:
Large copied templates should be avoided.

Actually:
They are the only available hook for login-button branding and custom sidebar links.

Why:
Seafile does not expose a plugin slot for these UI changes.

Do not change because:
Editing installed Seahub files would be untracked; removing the overrides removes the only visible panel entry points.

### seaf-cli container mounts the Docker socket (recorded host-root grant)

Looks like:
Mounting `/var/run/docker.sock` into a container is a misconfiguration.

Actually:
It is a deliberate, recorded grant so the NAS agent can apply panel-queued memory-limit updates (`GET /containers/{id}/json`, `POST /containers/{id}/update`) without SSH. Reviewed by the assigned reviewer (2026-10-26) with this entry as the recorded decision.

Why:
The panel cannot push to the NAS; the agent polls. Without the socket, the memory field is compose-only and requires an SSH recreate to change. The container is single-purpose on a private NAS and already runs as root with the live library bind mounts.

Do not change because:
Removing the mount silently degrades the feature to recreate-only; the panel then shows a stale "waiting for heartbeat" limit. If the grant is ever tightened, use a route-allowlisting proxy for exactly those two endpoints — not a generic socket proxy (POST passthrough still reaches container create/exec), and re-record the decision here. Blast radius while mounted: compromise of this container or its base image is root on `edgesynology1`.

### Folder sizes are cached, not calculated live

Looks like:
The file browser should compute folder sizes when you browse a directory.

Actually:
The NAS agent computes recursive source-folder sizes in the background and reports a cache to the Libraries page.

Why:
Live recursive walks over hundreds of thousands of files and multi-terabyte folders would be slow and disruptive.

Do not change because:
Live folder-size calculation would make browsing expensive and unreliable.

### Microsoft SSO uses internal `@auth.local` usernames

Looks like:
The `@auth.local` accounts are fake users that should be renamed to human emails.

Actually:
They are Seafile internal usernames for SSO-created users; human identity is in profile/contact email and OAuth bindings.

Why:
Seafile's OAuth flow creates internal user IDs and maps external identities separately.

Do not change because:
Renaming internal IDs casually can orphan OAuth bindings, library ownership, or profile rows.
