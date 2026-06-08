# seafile — POP Creations

Infrastructure for the Seafile Pro file sync deployment serving POP Creations designers.

8 designers in São Paulo access a file library that lives on Synology NAS devices in a NYC office. This repo contains everything to operate both sides of the system.

## Structure

```
seafile-server/               Linode VPS — live at seafile.designflow.app
├── seafile-server.yml        Docker Compose: Seafile, MariaDB, Redis
├── caddy.yml                 Docker Compose: Caddy reverse proxy + TLS
├── nas-settings.yml          Docker Compose: NAS sync settings web panel
├── .env.example              Environment variable template (never commit .env)
├── nas-settings/             Flask app — seaf-cli control panel (status/controls/config/libraries) + ingest window
├── custom-templates/         Seahub template overrides ("NAS Sync" sidebar links: sysadmin + main app)
└── docs/
    ├── architecture.md       System design, containers, data flow, storage
    ├── configuration.md      All env vars, config files, and their meanings
    ├── deployment.md         Start/stop, updates, backup, DNS, NAS image releases
    └── development.md        Logs, debugging, API usage, user management

synology-seaf-cli/            NYC Synology NAS — running on edgesynology1
├── Dockerfile                Wrapper image built on flrnnc/seafile-client
├── entrypoint.py             Fixed Seafile daemon entrypoint (replaces upstream default)
├── seaf-entrypoint.py        Date-filter staging wrapper; launches entrypoint.py
├── docker-compose.yml        One seaf-cli container per library
├── .env.example              NAS sync credentials template
└── README.md                 Synology setup and redeploy instructions

windows-workstation/          Windows rendering machine — seaf-cli + PopDAM agent
├── docker-compose.yml        seaf-cli containers (sources via CIFS from NAS over LAN)
├── setup.ps1                 One-shot installer: PopDAM agent + Docker + seaf-cli
└── README.md                 Machine replacement instructions

.github/workflows/
├── seaf-cli-image.yml        Lint + test + build + push seaf-cli wrapper image to GHCR
└── nas-settings-image.yml    Lint + test + build + push nas-settings panel image to GHCR
```

## Live System

| | |
|---|---|
| URL | https://seafile.designflow.app |
| Server | Linode VPS · 172.233.14.233 · Ubuntu 24.04 · Seafile Pro `13.0-latest` |
| Admin | `albert@popcre.com` via M365 SSO; local fallbacks `u2giants@gmail.com` and break-glass `albert` |
| Images (GHCR) | `:seaf-cli-latest` and `:nas-settings-latest` (+ immutable `:sha-<commit>` / `:nas-settings-sha-<commit>` per build) |
| Branch model | `main` only — no branches, no PRs |
| Credentials | `/opt/seafile/CREDENTIALS.txt` on the VPS (root-only, never in this repo) |
| GitHub | https://github.com/u2giants/seafile |

> **Current status (verified 2026-06-07):** VPS server and both NAS seaf-cli containers are **running**; NAS → S3 sync is up. The site has not gone live (designers not yet onboarded). See `AGENTS.md` → Pending Work / Critical Incident Log.

## AI Sessions

Start with **`AGENTS.md`** in this repo root. All context is there.
