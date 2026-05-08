# Seafile Pro — POP Creations

This directory contains everything needed to understand, operate, and maintain the Seafile Pro instance serving POP Creations.

---

## What This Is

Seafile Pro is a self-hosted file sync and share platform. It is deployed on a Linode VPS and serves as a geographically local relay for 8 designers in São Paulo, Brazil who need fast access to a 28TB file library that physically lives on Synology NAS devices in a New York City office.

**The flow:**
```
NYC Synology NAS ──(seaf-cli sync)──► Linode VPS / Seafile ──(HTTPS)──► São Paulo designers
     (source of truth)                  (relay / cache)                    (end users)
```

The NAS pushes files to Seafile via `seaf-cli` running in Docker on the Synology. Designers access Seafile directly over HTTPS. The VPS is the fast endpoint for Brazil; the NAS is the master copy.

---

## Quick Reference

| Item | Value |
|------|-------|
| URL | https://seafile.designflow.app |
| Server IP | 172.233.14.233 |
| Server type | Linode VPS, Ubuntu 24.04 LTS |
| RAM | 4GB |
| Disk | 80GB (VPS local) |
| Storage backend | Local disk (`/opt/seafile-data`) |
| Admin email | u2giants@gmail.com |
| Credentials file | `/opt/seafile/CREDENTIALS.txt` (root-only, chmod 600) |
| Seafile version | 13.0 Pro |
| Deployed | 2026-05-07 |
| DNS managed via | Cloudflare (zone: designflow.app) |
| Cloudflare zone ID | 921eb133a3f7d5802780445b283f84ce |

---

## Documentation Index

| File | What it covers |
|------|---------------|
| [README.md](README.md) | This file — overview and quick reference |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the system is built — containers, networking, data flows |
| [OPERATIONS.md](OPERATIONS.md) | Day-to-day operations — start/stop, logs, backup, updates |
| [CONFIGURATION.md](CONFIGURATION.md) | All config files, environment variables, and their meanings |
| [PENDING.md](PENDING.md) | What still needs to be done (SSO, NAS sync, S3) |

---

## Current Status (as of 2026-05-07)

- ✅ Server provisioned and hardened (UFW, SSH only)
- ✅ Docker installed, all images pulled and cached
- ✅ Seafile Pro 13.0 running with valid Let's Encrypt TLS certificate
- ✅ DNS: `seafile.designflow.app → 172.233.14.233` (DNS-only, Cloudflare proxy OFF)
- ✅ Seafile Pro license installed at `/opt/seafile-data/seafile-license.txt`
- ✅ Admin account: u2giants@gmail.com
- ✅ Daily MySQL backup cron (3am) + 30-day cleanup cron (4am)
- ✅ Docker and containerd enabled on system boot
- ⏳ Google OAuth SSO — not yet configured (needs Google Cloud OAuth credentials from Albert)
- ⏳ NAS sync service account (nas-sync@popcreations.com) — not yet created
- ⏳ Seafile libraries (Active Projects, Assets, Seasonal) — not yet created
- ⏳ Designer user accounts — not yet created
- ⏳ S3 storage backend — not configured (currently using local disk)
