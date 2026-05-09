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
├── nas-settings/             Flask app — NAS ingest window settings UI
├── custom-templates/         Seahub template overrides (sysadmin panel nav injection)
└── docs/
    ├── architecture.md       System design, containers, data flow, storage
    ├── configuration.md      All env vars, config files, and their meanings
    ├── deployment.md         Start/stop, updates, backup, DNS
    └── development.md        Logs, debugging, API usage, user management

synology-seaf-cli/            NYC Synology NAS — running on edgesynology1
├── docker-compose.yml        One seaf-cli container per library
├── seaf-entrypoint.py        Staging wrapper (date filter + hourly refresh)
├── .env.example              NAS sync credentials template
└── README.md                 Synology setup and redeploy instructions
```

## Live System

| | |
|---|---|
| URL | https://seafile.designflow.app |
| Server | Linode VPS · 172.233.14.233 · Ubuntu 24.04 |
| Admin | albert@popcre.com via M365 SSO |
| Credentials | `/opt/seafile/CREDENTIALS.txt` on the VPS (root-only, never in this repo) |
| GitHub | https://github.com/u2giants/seafile |

## AI Sessions

Start with **`AGENTS.md`** in this repo root. All context is there.
