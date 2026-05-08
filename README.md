# seafile — POP Creations

Infrastructure for the Seafile Pro file sync deployment serving POP Creations designers.

8 designers in São Paulo access a 28TB file library that lives on Synology NAS devices in a NYC office. This repo contains everything to operate both sides of the system.

## Structure

```
seafile-server/               Linode VPS — live at seafile.designflow.app
├── seafile-server.yml        Docker Compose: Seafile, MariaDB, Redis
├── caddy.yml                 Docker Compose: Caddy reverse proxy + TLS
├── .env.example              Environment variable template (never commit .env)
├── START_SEAFILE.sh          Pre-flight startup script
├── CONFIGURE_OAUTH.sh        Google OAuth SSO setup (already run — idempotent)
├── CREATE_NAS_SYNC_ACCOUNT.sh  NAS machine account + library creation
└── docs/
    ├── README.md             Server status and quick reference
    ├── architecture.md       System design, containers, data flow, storage
    ├── configuration.md      All env vars, config files, and their meanings
    ├── deployment.md         Start/stop, updates, backup, DNS, remaining work
    ├── development.md        Logs, debugging, API usage, user management
    └── CONTEXT_FOR_AI.md     Key facts for AI sessions picking up this project

synology-seaf-cli/            NYC Synology NAS — NOT YET DEPLOYED
├── docker-compose.yml        One seaf-cli container per library, UUIDs pre-filled
├── .env.example              NAS sync password template
└── README.md                 Synology setup instructions
```

## Live System

| | |
|---|---|
| URL | https://seafile.designflow.app |
| Server | Linode VPS · 172.233.14.233 · Ubuntu 24.04 |
| Admin (SSO) | u2giants@gmail.com via Google |
| Admin (local) | albert@popcre.com |
| Credentials | `/opt/seafile/CREDENTIALS.txt` on the VPS (root-only, never in this repo) |
| GitHub | https://github.com/u2giants/seafile |

## AI Sessions

Start with [`seafile-server/docs/CONTEXT_FOR_AI.md`](seafile-server/docs/CONTEXT_FOR_AI.md).
