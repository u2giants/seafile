# nas-settings

Flask web app that lets Seafile admins configure the NAS ingest window (how many days back each library syncs) without editing files or restarting containers.

Accessible at `https://seafile.designflow.app/nas-settings/` via a link in the Seafile System Admin sidebar.

## Auth

No separate login. On every request the app reads the browser's `sessionid` cookie (set by Seafile) and calls `GET http://seafile:8000/api/v2.1/admin/sysinfo/` internally to verify it belongs to a Seafile system admin. Non-admins and unauthenticated users are redirected to `/oauth/login/`.

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

## State

Settings are persisted to `/data/settings.json` inside the `nas-settings-data` Docker volume.

## Build and deploy

```bash
# Build (run from seafile-server/ — the build context is ./nas-settings)
cd /home/ai/seafile-repo/seafile-server
docker compose -f nas-settings.yml build nas-settings

# Deploy / restart
cd /opt/seafile
docker compose -f seafile-server.yml -f caddy.yml \
  -f /home/ai/seafile-repo/seafile-server/nas-settings.yml \
  up -d nas-settings
```

## Environment variables

| Variable | Source | Purpose |
|----------|--------|---------|
| `SECRET_KEY` | `.env` → `NAS_SETTINGS_SECRET_KEY` | Flask session signing |
| `SEAFILE_INTERNAL_URL` | hardcoded in `nas-settings.yml` | Base URL for internal Seafile API calls |
| `SEAFILE_PUBLIC_HOST` | hardcoded in `nas-settings.yml` | Host header sent with internal API calls |
