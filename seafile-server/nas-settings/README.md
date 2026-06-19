# nas-settings

Flask web app that gives the Seafile server's web UI a **GUI for the seaf-cli client**
running on the NAS — everything seaf-cli can do via the command line, surfaced as
admin controls. It also owns per-library ingest-window and sync-schedule settings.

Accessible at `https://seafile.designflow.app/nas-settings/` via a link in the Seafile
System Admin sidebar.

## Pages (tabs)

| Tab | seaf-cli equivalent | What it does |
|-----|---------------------|--------------|
| **Dashboard** | `status` | Live per-library sync state, commit/inotify verification, progress, errors, staging/ingest info; pause/resume. |
| **Controls** | `start` / `stop` / auto-sync | Pause, resume, restart daemon, stop daemon, verify now, write canary. |
| **Config** | `config -k [-v]` | Get/set any daemon config key (upload/download limits, TLS verify, …) plus a free-form key/value. |
| **Libraries** | `list`, `list-remote`, `create`, `desync` | Local libraries + desync; list server libraries; create a server library; show cached NAS folder sizes. |
| **Ingest Window** | — | Per-library ingest-day window plus weekday/weekend sync schedules. |

### Safety tiers
- **Read / Safe** (status, list, config get/set, pause/resume/restart/stop, verify now, write canary) apply directly.
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

Everything is keyed by **library UUID**. In the current single NAS container, `entrypoint.py`
discovers `SEAF_LIBRARY_<KEY>` variables and POSTs one heartbeat per UUID; the legacy
single-library `SEAF_LIBRARY` variable is only for compatibility. Admin actions in the browser call
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
| Sync schedule check | 30 s | The status heartbeat receives the current schedule and enables/disables per-repo `auto-sync`; weekday and weekend windows can differ. |
| Folder-size cache refresh | Nightly after 2 AM New York time | The NAS agent walks `/source` in the background and reports cached recursive sizes; the Libraries page never calculates folder sizes live. |

## Tests

`test_app.py` drives the Flask test client through template rendering, the command-queue
tiers/confirm gating, UUID routing, result persistence, and weekday/weekend schedule
serialization — no live Seafile/NAS needed:

```bash
cd seafile-server/nas-settings
pip install flask && python test_app.py
```

Run in CI by `.github/workflows/nas-settings-image.yml`. The NAS-side dispatcher has its own
stubbed test in `.github/workflows/seaf-cli-image.yml` via `synology-seaf-cli/test_entrypoint.py`.

## Auth

No separate login. On every request the app reads the browser's `seahub_auth` cookie (set by Seafile) and calls Seafile's admin sysinfo API with token auth to verify it belongs to a Seafile system admin. Non-admins and unauthenticated users are redirected to the Seafile login with `next=/nas-settings/`.

The `seafile` service name resolves because both containers are on `seafile-net`.

## Public API endpoint

`GET /nas-settings/api/settings` — no auth required. Returns non-secret JSON keyed by
container name:

```json
{
  "seaf-cli-char-licensed": {
    "ingest_days": 730,
    "uuid": "177cf9de-...",
    "schedule": {
      "enabled": true,
      "timezone": "America/New_York",
      "windows": {
        "weekdays": {
          "enabled": true,
          "days": [0, 1, 2, 3, 4],
          "start": "19:00",
          "end": "07:00"
        },
        "weekends": {
          "enabled": false,
          "days": [5, 6],
          "start": "09:00",
          "end": "17:00"
        }
      }
    }
  }
}
```

The NAS seaf-cli containers poll this endpoint hourly for ingest-window changes and receive
the current schedule on each 30-second status heartbeat. `ingest_days: null` means
"all files, no limit". Schedule day numbers use Python's `weekday()` convention:
Monday is `0`, Sunday is `6`. If a window's end time is earlier than its start time,
the window runs overnight.

## Independent sync verification

Each NAS status heartbeat can include a `verification` object produced by the
seaf-cli wrapper. The dashboard shows it separately from Seafile's daemon state so
admins can see whether "synchronized" was independently confirmed.

When the NAS wrapper sees a repo report `synchronized`, it compares the client's
synced commit head with the server repo head, scans the daemon log for inotify
watch failures, reports inotify watch usage/limits, and checks a per-library canary
file. Any failure is reported as `anomaly` with diagnostics. The wrapper does not
auto-restart the daemon; restart can temporarily hide an inotify-watch failure by
forcing a one-time scan while leaving the host kernel limit broken.

`seafile-ignore.txt` is hygiene, not the inotify repair: Synology will keep regenerating local `@eaDir` trees, existing server-side `@eaDir` content must be deleted separately, and the required fix for false-synchronized drift is raising the host inotify watch limit.

Controls exposes two safe commands for manual checks:

| Command | Effect |
|---------|--------|
| `verify_now` | Runs the commit-head, inotify/log, and canary verification immediately. |
| `write_canary` | Forces a new `.seafile-sync-canary.json` write, then verifies it. |

## API endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/settings` | none | Containers poll this for per-library `ingest_days` and schedule metadata. |
| `POST /api/status` | `X-Status-Token` | Containers report state + command results; response carries the next queued command, or the current schedule when no command is queued. |
| `GET /api/status-data` | admin session | Browser polls this: per-library status, staleness, pending commands, recent results. |
| `POST /api/command` | admin session | Enqueue a command `{library_uuid, verb, args, confirm}`. |

`refresh_folder_sizes` is a safe command that asks the NAS agent to rebuild its cached
recursive folder-size table immediately. Otherwise the cache refreshes nightly.
`verify_now` and `write_canary` are safe commands used by the independent verification
guard.

## State

Persisted under `/data/` inside the `nas-settings-data` Docker volume:

| File | Contents |
|------|----------|
| `settings.json` | Per-library ingest window and weekday/weekend sync schedule. |
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
docker compose --env-file /opt/seafile/.env \
  -f /home/ai/seafile-repo/seafile-server/nas-settings.yml \
  pull nas-settings
docker compose --env-file /opt/seafile/.env \
  -f /home/ai/seafile-repo/seafile-server/nas-settings.yml \
  up -d --force-recreate nas-settings
docker logs --tail 80 nas-settings
```

Healthy logs include repeated `POST /api/status HTTP/1.1" 200` entries. With the
current single NAS `seaf-cli` container, seeing three POSTs roughly every 30 seconds
means all three configured library UUIDs are reporting.

Rollback: pin `image:` in `nas-settings.yml` to a prior `:nas-settings-sha-<commit>` and `up -d`.

## Environment variables

| Variable | Source | Purpose |
|----------|--------|---------|
| `SECRET_KEY` | `.env` → `NAS_SETTINGS_SECRET_KEY` | Flask session signing |
| `STATUS_TOKEN` | `.env` → `NAS_STATUS_TOKEN` (shared with each seaf-cli container's `SEAF_STATUS_TOKEN`) | Authenticates container status POSTs and gates command handback |
| `SEAFILE_INTERNAL_URL` | hardcoded in `nas-settings.yml` | Base URL for internal Seafile API calls |
| `SEAFILE_PUBLIC_HOST` | hardcoded in `nas-settings.yml` | Host header sent with internal API calls |
