# nas-settings

Flask web app that gives the Seafile server's web UI a **GUI for the seaf-cli client**
running on the NAS — everything seaf-cli can do via the command line, surfaced as
admin controls. It also keeps the original ingest-window settings.

Accessible at `https://seafile.designflow.app/nas-settings/` via a link in the Seafile
System Admin sidebar.

## Pages (tabs)

| Tab | seaf-cli equivalent | What it does |
|-----|---------------------|--------------|
| **Dashboard** | `status` | Live per-library sync state, progress, errors, staging/ingest info; pause/resume. |
| **Controls** | `start` / `stop` / auto-sync | Pause, resume, restart daemon, stop daemon. |
| **Config** | `config -k [-v]` | Get/set any daemon config key (upload/download limits, TLS verify, …) plus a free-form key/value. |
| **Libraries** | `list`, `list-remote`, `create`, `desync` | Local libraries + desync; list server libraries; create a server library; show cached NAS folder sizes. |
| **Ingest Window** | — | The original per-library ingest-day window. |

### Safety tiers
- **Read / Safe** (status, list, config get/set, pause/resume/restart/stop) apply directly.
- **Guarded** (`desync`, `create`, re-`init`) require typing the library name to confirm; the
  server also rejects them unless the request carries `confirm: true`.
- **Guidance-only**: `download` / `sync` of a *brand-new* NAS folder can't be done to a
  running container (the source is a baked-in read-only bind-mount), so the Libraries page
  shows the exact compose edit + redeploy steps instead of a button.

## How control works (the bridge)

The server cannot reach the NAS directly, so it never pushes. Instead the seaf-cli
container's `entrypoint.py` **polls** every 30 s:

1. Container POSTs `/api/status` (authenticated by `SEAF_STATUS_TOKEN`) with its current
   state and the results of any command it just ran.
2. The server persists the status and **hands back the next queued command** in the
   response: `{command: {id, verb, args}}`.
3. The container runs it (via the daemon RPC for pause/resume, otherwise `seaf-cli`) and
   reports the result on its next POST.

Everything is keyed by **library UUID** (`SEAF_LIBRARY`) — stable and known to both sides —
not the container's ephemeral Docker hostname. Admin actions in the browser call
`POST /api/command {library_uuid, verb, args, confirm}`, which enqueues the command.

## Heartbeat timing

| Loop | Interval | Notes |
| --- | ---: | --- |
| Container status heartbeat | 30 s | POSTs `/api/status`, delivers command results, and receives the next queued command. |
| Browser dashboard refresh | 10 s | GETs `/api/status-data`; the UI can only show new NAS data after the next heartbeat. |
| Offline/stale threshold | 120 s | Four missed heartbeats marks a library offline. |
| seaf-daemon watchdog | 10 s | Container exits if the daemon PID disappears, letting Docker restart it. |
| Docker healthcheck | 60 s | Runs the image healthcheck with 10 s timeout and 3 retries. |
| Ingest-window refresh | 1 h | Rebuilds the staged `/library` view and re-reads `/api/settings`. |
| Folder-size cache refresh | Nightly after 2 AM New York time | The NAS agent walks `/source` in the background and reports cached recursive sizes; the Libraries page never calculates folder sizes live. |

## Tests

`test_app.py` drives the Flask test client through template rendering, the command-queue
tiers/confirm gating, UUID routing, and result persistence — no live Seafile/NAS needed:

```bash
cd seafile-server/nas-settings
pip install flask && python test_app.py
```

Run in CI by `.github/workflows/nas-settings-test.yml`. The NAS-side dispatcher has its own
stubbed test at `synology-seaf-cli/test_entrypoint.py`.

## Auth

No separate login. On every request the app reads the browser's `sessionid` cookie (set by Seafile) and calls `GET http://seafile/api/v2.1/admin/sysinfo/` internally to verify it belongs to a Seafile system admin. Non-admins and unauthenticated users are redirected to the Seafile login with `next=/nas-settings/`.

The `seafile` service name resolves because both containers are on `seafile-net`.

## Public API endpoint

`GET /nas-settings/api/settings` — no auth required. Returns JSON keyed by container name:

```json
{
  "seaf-cli-char-licensed": {"ingest_days": 730, "uuid": "177cf9de-..."},
  "seaf-cli-generic-decor": {"ingest_days": 730, "uuid": "1b116ab7-..."}
}
```

The NAS seaf-cli containers poll this endpoint hourly to pick up ingest window changes without a restart. `ingest_days: null` means "all files, no limit".

## API endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/settings` | none | Containers poll this for per-library `ingest_days` (see below). |
| `POST /api/status` | `X-Status-Token` | Containers report state + command results; response carries the next queued command. |
| `GET /api/status-data` | admin session | Browser polls this: per-library status, staleness, pending commands, recent results. |
| `POST /api/command` | admin session | Enqueue a command `{library_uuid, verb, args, confirm}`. |

`refresh_folder_sizes` is a safe command that asks the NAS agent to rebuild its cached
recursive folder-size table immediately. Otherwise the cache refreshes nightly.

## State

Persisted under `/data/` inside the `nas-settings-data` Docker volume:

| File | Contents |
|------|----------|
| `settings.json` | Per-library ingest window. |
| `status.json` | Latest status report per library UUID. |
| `commands.json` | FIFO queue of pending commands per library UUID. |
| `results.json` | Most recent command results per library UUID (capped at 25). |

## Build and deploy

The image is **built by CI** (`.github/workflows/nas-settings-image.yml`) and published to
GHCR as `ghcr.io/u2giants/seafile:nas-settings-latest` (+ `:nas-settings-sha-<commit>`).
Deploy = **pull** that image — do not build on the VPS (§25 model; see AGENTS.md → Deployment).

```bash
# 1. Commit changes under seafile-server/nas-settings/ to main; wait for the
#    "nas-settings image" workflow to publish: https://github.com/u2giants/seafile/actions
# 2. Pull + recreate on the VPS:
cd /opt/seafile
docker compose -f seafile-server.yml -f caddy.yml \
  -f /home/ai/seafile-repo/seafile-server/nas-settings.yml \
  pull nas-settings
docker compose -f seafile-server.yml -f caddy.yml \
  -f /home/ai/seafile-repo/seafile-server/nas-settings.yml \
  up -d nas-settings
```

Rollback: pin `image:` in `nas-settings.yml` to a prior `:nas-settings-sha-<commit>` and `up -d`.

## Environment variables

| Variable | Source | Purpose |
|----------|--------|---------|
| `SECRET_KEY` | `.env` → `NAS_SETTINGS_SECRET_KEY` | Flask session signing |
| `STATUS_TOKEN` | `.env` → `NAS_STATUS_TOKEN` (shared with each seaf-cli container's `SEAF_STATUS_TOKEN`) | Authenticates container status POSTs and gates command handback |
| `SEAFILE_INTERNAL_URL` | hardcoded in `nas-settings.yml` | Base URL for internal Seafile API calls |
| `SEAFILE_PUBLIC_HOST` | hardcoded in `nas-settings.yml` | Host header sent with internal API calls |
