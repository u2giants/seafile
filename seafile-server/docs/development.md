# Development & Operations

## Logs

### Container stdout logs
```bash
docker logs seafile          # Seafile app (startup, fatal errors)
docker logs seafile-caddy    # TLS, routing
docker logs seafile-mysql    # Database
docker logs seafile-redis    # Cache
docker logs -f seafile       # Follow live
```

### Application logs (more detailed, inside volume)
```bash
ls /opt/seafile-data/seafile/logs/
```

| File | Contents |
|------|----------|
| `seahub.log` | Web UI requests and Django errors |
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
```

## Troubleshooting

**502 Bad Gateway** — Seafile is initialising. Normal for 3–5 minutes after first start. `docker logs -f seafile` and wait for "Seafile server started".

**"Commits, fs and blocks should use different buckets"** — Three S3 buckets must have distinct names. Check `S3_COMMIT_BUCKET`, `S3_FS_BUCKET`, `S3_BLOCK_BUCKET` in `.env`.

**"Seafile server started" never appears** — Check `docker logs seafile 2>&1 | grep -i "error\|fail\|kill"`. Common causes: S3 bucket misconfiguration, missing JWT_PRIVATE_KEY, license file not found.

**Login fails with correct password** — Check `seahub_settings.py` for syntax errors (duplicate OAuth blocks, bad indentation). Run syntax check above. `docker restart seafile` after any fix.

**Google SSO button missing** — `ENABLE_OAUTH = True` missing or seahub_settings.py has a syntax error.

**TLS certificate error** — DNS not resolved yet, or Let's Encrypt couldn't reach port 80. Check `docker logs seafile-caddy`.

**Container keeps restarting** — `docker logs seafile 2>&1 | tail -30` — look at the lines immediately before each restart.

## Seafile API

All management can be done via the REST API. Get a token first:

```bash
TOKEN=$(curl -s \
  -d "username=u2giants@gmail.com&password=$(grep INIT_SEAFILE_ADMIN_PASSWORD /opt/seafile/.env | cut -d= -f2)" \
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

# List all libraries for a user
curl -s "https://seafile.designflow.app/api2/repos/" \
  -H "Authorization: Token $USER_TOKEN"
```

**API note on user emails:** Seafile internally assigns accounts a UUID-based email (`<hash>@auth.local`). The human email is stored as `contact_email`. When using the admin API to modify a user, use the internal email, not the contact email. Get it from the user list response.

## Managing Users

### Add a user (admin panel)
Admin Panel → Users → Add User → email, password, role: Default User.

### Designer onboarding via Google SSO
Send designers `https://seafile.designflow.app`. They click "Sign in with Google" — account is auto-created on first login. Then share libraries:

```bash
# Share via web UI: open library → Share icon → Share to User → email → Read/Write
# Or via API (as the library owner):
NAS_TOKEN=$(curl -s -d "username=nas-sync@popcre.com&password=PASS" \
  https://seafile.designflow.app/api2/auth-token/ | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s -X PUT "https://seafile.designflow.app/api2/repos/<UUID>/dir/shared_items/?p=/" \
  -H "Authorization: Token $NAS_TOKEN" \
  -d "share_type=user&username=designer@example.com&permission=rw"
```

### Admin panel
https://seafile.designflow.app/sys/useradmin/

Login: `u2giants@gmail.com` (SSO) or `albert@popcre.com` (password).
