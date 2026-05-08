# Seafile Pro — POP Creations

Infrastructure repo for the Seafile Pro deployment serving POP Creations designers.

## What This Is

8 designers in São Paulo access a 28TB file library that lives on Synology NAS devices in a NYC office. This repo contains everything needed to deploy and maintain both sides of the system.

## Structure

```
seafile-server/          ← Linode VPS deployment (live at seafile.designflow.app)
├── seafile-server.yml   ← Docker Compose: Seafile, MariaDB, Redis
├── caddy.yml            ← Docker Compose: Caddy reverse proxy + TLS
├── .env.example         ← Environment variable template (copy to .env, fill secrets)
├── START_SEAFILE.sh     ← Pre-flight startup script
├── CONFIGURE_OAUTH.sh   ← Google OAuth SSO setup
├── CREATE_NAS_SYNC_ACCOUNT.sh
└── docs/
    ├── README.md        ← Status and quick reference
    ├── ARCHITECTURE.md  ← System design, containers, data flow
    ├── OPERATIONS.md    ← Start/stop, logs, backup, updates
    ├── CONFIGURATION.md ← All config files explained
    ├── PENDING.md       ← Remaining work + step-by-step instructions
    └── CONTEXT_FOR_AI.md ← Key facts for AI sessions working on this system

synology-seaf-cli/       ← NYC Synology NAS sync containers (not yet deployed)
├── docker-compose.yml   ← One seaf-cli container per library
├── .env.example         ← NAS sync password template
└── README.md            ← Synology setup instructions
```

## Quick Reference

| Item | Value |
|------|-------|
| Live URL | https://seafile.designflow.app |
| Server | Linode VPS — 172.233.14.233 |
| Admin | u2giants@gmail.com (Google SSO) or albert@popcre.com (local) |
| Credentials | `/opt/seafile/CREDENTIALS.txt` on the VPS (root-only, never in this repo) |

## AI Sessions

Start with `seafile-server/docs/CONTEXT_FOR_AI.md` — written specifically for AI assistants picking up this project.
