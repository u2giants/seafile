# Context for AI Sessions

This file is written specifically for a future AI assistant working on this system. Read this before doing anything else.

---

## Who You're Working For

**Albert** (u2giants@gmail.com) is the operator. He runs POP Creations, a design agency. He is comfortable with technical work but delegates infrastructure management to AI sessions via Claude Code running on this VPS.

---

## What This System Is

A Seafile Pro 13.0 file sync server for POP Creations, hosted on a Linode VPS at `172.233.14.233`. It serves 8 graphic designers in São Paulo, Brazil who work with a 28TB file library that lives on Synology NAS devices in a New York City office.

**The core architecture:** NAS (NYC) → Seafile server (this VPS) ← Designers (São Paulo)

The VPS is a relay, not the source of truth. The NAS holds the real files; Seafile is the access layer.

---

## Key Facts You Need

### Access
- You are running as `ai` user with passwordless sudo
- Working directory for Seafile: `/opt/seafile/`
- All scripts and configs are in `/opt/seafile/`
- Credentials (passwords, UUIDs, keys): `/opt/seafile/CREDENTIALS.txt` (root-only)

### Credentials (do not store elsewhere, read from file)
Read credentials from `/opt/seafile/CREDENTIALS.txt`. Do not hardcode them anywhere.

### The application is live
- https://seafile.designflow.app is running and accessible
- Do not stop containers without telling Albert first
- Changes to seahub_settings.py require `docker restart seafile`
- Changes to `.env` require `docker compose -f /opt/seafile/seafile-server.yml -f /opt/seafile/caddy.yml up -d`

### DNS
- `seafile.designflow.app` A record → `172.233.14.233`
- **DNS-only, NOT proxied through Cloudflare** — this is intentional, do not change it
- Cloudflare zone ID: `921eb133a3f7d5802780445b283f84ce`
- Cloudflare account ID: `8303d11002766bf1cc36bf2f07ba6f20`
- Cloudflare MCP is available in Claude Code but has NO DNS tools — use the Cloudflare API via curl with a bearer token if Albert provides one

### Docker
```bash
# Check status
docker compose -f /opt/seafile/seafile-server.yml -f /opt/seafile/caddy.yml ps

# Restart all
cd /opt/seafile && docker compose -f seafile-server.yml -f caddy.yml restart

# Logs
docker logs seafile
docker logs seafile-caddy
```

### The four containers
| Container | Image | Role |
|-----------|-------|------|
| `seafile` | `seafileltd/seafile-pro-mc:13.0-latest` | Main app |
| `seafile-caddy` | `lucaslorentz/caddy-docker-proxy:2.12-alpine` | TLS + reverse proxy |
| `seafile-mysql` | `mariadb:10.11` | Database |
| `seafile-redis` | `redis:latest` | Cache |

---

## Things That Are Not Obvious

### Image name correction
The Seafile manual and original deployment doc reference `docker.seadrive.org/seafileltd/seafile-pro-mc:13.0-latest`. This tag **does not exist** on the Seafile private registry. The correct image for Seafile Pro 13.0 is `seafileltd/seafile-pro-mc:13.0-latest` from **Docker Hub**. The `latest` tag does exist on docker.seadrive.org.

### No Elasticsearch
`seafevents.conf` has `[INDEX FILES]` enabled pointing to `es_host = elasticsearch`, but there is no Elasticsearch container. Full-text search inside files does not work. Filename search works. This is intentional for now (Elasticsearch needs ~2GB RAM on a 4GB server). See PENDING.md to add it.

### S3 storage not configured
File data is currently on local disk at `/opt/seafile-data/seafile/seafile-data/`. The 80GB VPS disk will not hold 28TB. S3 configuration is pending — see PENDING.md. Do NOT let the NAS start a full sync before this is resolved.

### Cloudflare proxy MUST stay off
`seafile.designflow.app` is DNS-only. If it were proxied, Seafile's sync protocol (non-HTTP binary protocol on port 8082) would break. Never enable the orange cloud for this record.

### seahub_settings.py is inside the volume
`/opt/seafile-data/seafile/conf/seahub_settings.py` is inside the Docker volume. It persists across container restarts but is regenerated on fresh container creation if the volume doesn't exist. Always back it up before editing.

### Google OAuth is not yet configured
The login page currently shows email/password only. No "Sign in with Google" button exists yet. See PENDING.md item 1 for setup instructions.

### WebDAV is disabled
`seafdav.conf` has `enabled = false`. Can be enabled without opening new ports (Caddy handles it on 443).

---

## Helper Scripts

All scripts are in `/opt/seafile/` and should be run as root.

| Script | Purpose | When to use |
|--------|---------|------------|
| `START_SEAFILE.sh` | Pre-flight check + start containers | After a server reboot or new deployment |
| `CONFIGURE_OAUTH.sh CLIENT_ID SECRET` | Add Google OAuth to seahub_settings.py + restart | When Albert provides Google OAuth credentials |
| `CREATE_NAS_SYNC_ACCOUNT.sh` | Create nas-sync@popcreations.com + 3 libraries | One-time setup before NAS sync begins |

---

## What Still Needs To Be Done

See `PENDING.md` for full details. Summary:
1. **Google OAuth SSO** — Albert needs to create a Google Cloud OAuth app
2. **NAS sync account** — run `CREATE_NAS_SYNC_ACCOUNT.sh`
3. **Libraries** — created by the above script (Active Projects, Assets, Seasonal)
4. **Designer accounts** — 8 users to be added
5. **Synology NAS configuration** — seaf-cli Docker setup on the NYC NAS
6. **S3 storage** — IMPORTANT: must be configured before large-scale sync begins

---

## Files in This Repository

```
/opt/seafile/
├── .env                         ← All secrets and runtime config
├── seafile-server.yml           ← Docker compose: db, redis, seafile
├── caddy.yml                    ← Docker compose: Caddy TLS proxy
├── CREDENTIALS.txt              ← All passwords and UUIDs (root-only)
├── START_SEAFILE.sh             ← Startup script with pre-flight checks
├── CONFIGURE_OAUTH.sh           ← Google OAuth setup helper
├── CREATE_NAS_SYNC_ACCOUNT.sh   ← NAS service account + library creation
├── oauth_settings_template.py   ← Reference copy of the OAuth config block
└── docs/
    ├── README.md                ← Overview and current status
    ├── ARCHITECTURE.md          ← System design and container layout
    ├── OPERATIONS.md            ← How to operate the system day-to-day
    ├── CONFIGURATION.md         ← All config files explained
    ├── PENDING.md               ← Remaining work with step-by-step instructions
    └── CONTEXT_FOR_AI.md        ← This file
```
