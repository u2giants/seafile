# Seafile Pro Server — POP Creations

**Live at:** https://seafile.designflow.app  
**Server:** Linode VPS · 172.233.14.233 · Ubuntu 24.04 LTS · 4GB RAM · 80GB disk

## Purpose

Relay server between the NYC Synology NAS (source of truth, 28TB) and 8 designers in São Paulo. Designers connect to this VPS over HTTPS; the NAS pushes files to it via seaf-cli. File data is stored in Linode Object Storage (São Paulo region), not on the VPS disk.

## Status

| Component | State |
|-----------|-------|
| Seafile Pro 13.0 | ✅ Running |
| TLS certificate (Let's Encrypt) | ✅ Valid, auto-renewing |
| DNS: seafile.designflow.app → 172.233.14.233 | ✅ DNS-only, no Cloudflare proxy |
| S3 storage (Linode, br-gru-1) | ✅ Configured — 3 buckets |
| Google OAuth SSO | ✅ Live |
| Admin accounts | ✅ u2giants@gmail.com (SSO) · albert@popcre.com (local) |
| NAS sync account | ✅ nas-sync@popcre.com |
| Libraries | ✅ Active Projects · Assets · Seasonal |
| Daily MySQL backup cron | ✅ 3am, 30-day retention |
| Synology seaf-cli containers | ⏳ Not yet deployed |
| Designer user accounts (8) | ⏳ Not yet created |
| Elasticsearch (full-text search) | ⏳ Not deployed — intentional (RAM) |

## Quick Reference

| Item | Value |
|------|-------|
| Seafile version | 13.0 Pro |
| Compose dir | `/opt/seafile/` |
| Data dir | `/opt/seafile-data/` |
| Credentials | `/opt/seafile/CREDENTIALS.txt` (root-only) |
| Cloudflare zone | designflow.app · ID: `921eb133a3f7d5802780445b283f84ce` |
| S3 endpoint | `br-gru-1.linodeobjects.com` |
| S3 buckets | `seafile-s3` (blocks) · `seafile-s3-commits` · `seafile-s3-fs` |
| NAS sync account | nas-sync@popcre.com |
| Library: Active Projects | UUID `0dee1650-878e-4ca3-9533-e3876ebd4c1e` |
| Library: Assets | UUID `09afbd46-87c6-45b5-a305-431310af20a5` |
| Library: Seasonal | UUID `8108c1df-6dc1-4e22-bc1f-4eb8e8ef5d2b` |

## Docs

| File | Contents |
|------|----------|
| [architecture.md](architecture.md) | Containers, networking, storage, auth flow |
| [configuration.md](configuration.md) | All env vars and config files |
| [deployment.md](deployment.md) | Start/stop, updates, backup, remaining work |
| [development.md](development.md) | Logs, debugging, API, user management |
| [CONTEXT_FOR_AI.md](CONTEXT_FOR_AI.md) | Key facts for AI sessions |
