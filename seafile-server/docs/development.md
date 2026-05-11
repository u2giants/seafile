# Development & Operations

## Logs

### Container stdout logs
```bash
docker logs seafile          # Seafile app (startup, fatal errors)
docker logs seafile-caddy    # TLS, routing
docker logs seafile-mysql    # Database
docker logs seafile-redis    # Cache
docker logs nas-settings     # NAS settings panel (Flask startup, request errors)
docker logs -f seafile       # Follow live
```

### Application logs (more detailed, inside volume)
```bash
ls /opt/seafile-data/seafile/logs/
```

| File | Contents |
|------|----------|
| `seahub.log` | Web UI requests and Django errors — check here first for OAuth/login failures |
| `seafile.log` | File sync daemon, S3 operations |
| `seafevents.log` | Background jobs — includes expected Elasticsearch connection errors every 10m |
| `seafile-monitor.log` | Process monitor output |

## Common Debug Checks

```bash
# All containers healthy?
docker compose -f /opt/seafile/seafile-server.yml -f /opt/seafile/caddy.yml ps

# Site responding?
curl -sI https://seafile.designflow.app | head -3

# DNS correct?
dig +short seafile.designflow.app   # should return 172.233.14.233

# S3 reachable?
curl -s --aws-sigv4 "aws:amz:br-gru-1:s3" \
  --user "$(grep S3_KEY_ID /opt/seafile/.env | cut -d= -f2):$(grep S3_SECRET_KEY /opt/seafile/.env | cut -d= -f2)" \
  "https://br-gru-1.linodeobjects.com/" | grep -o '<Name>[^<]*</Name>'

# License valid?
cat /opt/seafile-data/seafile-license.txt
# Admin panel → System Info → Users limit (must not be 3)

# seahub_settings.py syntax OK?
docker exec seafile python3 -c "import ast; ast.parse(open('/shared/seafile/conf/seahub_settings.py').read()); print('OK')"

# nas-settings panel responding?
curl -sI https://seafile.designflow.app/nas-settings/   # should 302 to /oauth/login/ if not logged in
curl -s https://seafile.designflow.app/nas-settings/api/settings | python3 -m json.tool
```

## NAS seaf-cli Container Debugging

All docker commands on edgesynology1 must be base64-encoded via NAS MCP (target: edgesynology1).

```bash
# Check container status (both containers)
CMD="/var/packages/ContainerManager/target/usr/bin/docker ps --filter name=seaf-cli"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'

# Tail logs from a container
CMD="docker logs --tail 100 seaf-cli-char-licensed"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'

# Check health check status
CMD="docker inspect --format='{{.State.Health.Status}} {{.State.Health.FailingStreak}}' seaf-cli-char-licensed"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'

# Check process tree inside a container (verify tini + seaf-daemon running)
CMD="docker top seaf-cli-char-licensed"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'
```

### What healthy looks like

Container `docker top` should show approximately:
```
tini
  └── python3 /home/seafile/seaf-entrypoint.py   ← Stage 1 (alive, owns refresh thread)
        └── python3 /home/seafile/entrypoint.py   ← Stage 2
              └── seaf-daemon                      ← sync daemon
```

Log output should cycle through:
```
seaf-entrypoint  Ingest window: 730 days — N qualifying files
seaf-entrypoint  Library ready — N files updated
[upstream]       Monitoring seaf-daemon (PID N)
[upstream]       synchronized
```

### What unhealthy looks like

- `seaf-daemon` absent from `docker top` but container still running → watchdog hasn't fired yet (10s poll) or restart loop
- Container restarting frequently → seaf-daemon dying; check network reachability to `seafile.designflow.app`
- Health check `unhealthy` → RPC socket not responding; seaf-daemon may be starting up or crashed
- No hourly refresh in logs → `seaf-entrypoint.py` exited before its refresh thread fired (shouldn't happen with current wrapper)

### If a container is stuck or needs a forced restart

```bash
CMD="docker restart seaf-cli-char-licensed"
echo "$CMD" | base64 | xargs -I{} bash -c 'echo {} | base64 -d | bash'
```

## Troubleshooting

**502 Bad Gateway** — Seafile is initialising. Normal for 3–5 minutes after first start. `docker logs -f seafile` and wait for "Seafile server started".

**"Commits, fs and blocks should use different buckets"** — Three S3 buckets must have distinct names. Check `S3_COMMIT_BUCKET`, `S3_FS_BUCKET`, `S3_BLOCK_BUCKET` in `.env`.

**"Seafile server started" never appears** — Check `docker logs seafile 2>&1 | grep -i "error\|fail\|kill"`. Common causes: S3 bucket misconfiguration, missing JWT_PRIVATE_KEY, license file not found.

**Login fails with correct password** — Check `seahub_settings.py` for syntax errors (duplicate OAuth blocks, bad indentation). Run syntax check above. `docker restart seafile` after any fix.

**M365 SSO "Error, please contact administrator"** — Check `seahub.log` for the exact error. Most likely cause: `OAUTH_ATTRIBUTE_MAP` has `'id': (True, 'sub')` — the `id` key must be `(False, 'sub')` (optional) since Microsoft's OIDC endpoint returns `sub` but not `id`. See [configuration.md](configuration.md) for the correct value.

**TLS certificate error** — DNS not resolved yet, or Let's Encrypt couldn't reach port 80. Check `docker logs seafile-caddy`.

**Container keeps restarting** — `docker logs seafile 2>&1 | tail -30` — look at the lines immediately before each restart.

**nas-settings redirects to login unexpectedly** — The panel calls `GET http://seafile:8000/api/v2.1/admin/sysinfo/` with the browser's `sessionid` cookie on every request to verify admin status. If that internal call fails (Seafile container down, network issue, non-admin session), access is denied. Check that the `seafile` container is healthy and the request carries a valid admin session cookie.

## Seafile API

Get a local-password token (use `albert@popcre.com` — `u2giants@gmail.com` may be SSO-only after first login):

```bash
TOKEN=$(curl -s \
  -d "username=albert@popcre.com&password=<password from CREDENTIALS.txt>" \
  https://seafile.designflow.app/api2/auth-token/ \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
```

### Common API calls

```bash
# List users
curl -s "https://seafile.designflow.app/api/v2.1/admin/users/" \
  -H "Authorization: Token $TOKEN" | python3 -m json.tool

# Create user
curl -s -X POST "https://seafile.designflow.app/api/v2.1/admin/users/" \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass","role":"default"}'

# Promote user to admin
curl -s -X PUT "https://seafile.designflow.app/api/v2.1/admin/users/<internal-email>@auth.local/" \
  -H "Authorization: Token $TOKEN" \
  -d "is_staff=true"

# List libraries
curl -s "https://seafile.designflow.app/api/v2.1/admin/libraries/" \
  -H "Authorization: Token $TOKEN" | python3 -m json.tool
```

**API note on user emails:** Seafile internally assigns accounts a UUID-based email (`<hash>@auth.local`). The human email is stored as `contact_email`. When using the admin API to modify a user, use the internal email, not the contact email. Get it from the user list response.

## Managing Users

### Designer onboarding via M365 SSO
Send designers `https://seafile.designflow.app`. They click "Sign in with Microsoft" — account is auto-created on first login (must have a POP Creations M365 account in the tenant). Then share libraries via the web UI: open library → Share icon → Share to User → email → Read/Write.

### Admin panel
https://seafile.designflow.app/sys/useradmin/

Login: M365 SSO or `albert@popcre.com` (password).
