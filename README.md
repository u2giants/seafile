# seafile — POP Creations

Infrastructure for the Seafile Pro file sync deployment serving POP Creations designers.

POP Creations designers access a file library that lives on Synology NAS devices in a NYC office. This repo contains everything to operate both sides of the system.

> Internal: see [docs/1password.md](docs/1password.md) for 1Password access (MCP server + op CLI).

## Structure

```
seafile-server/               Linode VPS — live at seafile.designflow.app
├── seafile-server.yml        Docker Compose: Seafile, MariaDB, Redis
├── caddy.yml                 Docker Compose: Caddy reverse proxy + TLS
├── nas-settings.yml          Docker Compose: NAS sync settings web panel
├── .env.example              Environment variable template (never commit .env)
├── nas-settings/             Flask app — seaf-cli control panel + ingest/schedule settings
└── custom-templates/         Seahub template overrides (Microsoft login button + NAS Sync sidebar links)

synology-seaf-cli/            NYC Synology NAS — running on edgesynology1
├── Dockerfile                Wrapper image built on flrnnc/seafile-client
├── entrypoint.py             Fixed Seafile daemon entrypoint (replaces upstream default)
├── seaf-entrypoint.py        Legacy staging wrapper kept for workflow/test compatibility
├── docker-compose.yml        Single NAS seaf-cli container with multi-library mounts
├── .env.example              NAS sync credentials template
└── README.md                 Synology setup and redeploy instructions

.github/workflows/
├── seaf-cli-image.yml        Lint + test + build + push seaf-cli wrapper image to GHCR
└── nas-settings-image.yml    Lint + test + build + push nas-settings panel image to GHCR

docs/                         INDEX.md (generated index) plus architecture,
                              configuration, deployment, development, incidents,
                              idiosyncrasies, identifiers, pending-work, and
                              agents-reference — see docs/INDEX.md
```

Folder guides: [nas-settings panel](seafile-server/nas-settings/README.md), [custom templates](seafile-server/custom-templates/README.md), [Synology seaf-cli](synology-seaf-cli/README.md).

## Live System

| | |
|---|---|
| URL | https://seafile.designflow.app |
| Server | Linode VPS · 172.233.14.233 · Ubuntu 24.04 · Seafile Pro `13.0-latest` |
| Admin | `albert@popcre.com` via M365 SSO; internal Seafile username `4cba3f5721f7436fbe06a2b154ee296a@auth.local` |
| Images (GHCR) | `:seaf-cli-latest` and `:nas-settings-latest` (+ immutable `:sha-<commit>` / `:nas-settings-sha-<commit>` per build) |
| Branch model | Pull requests to `main`; never push directly to `main` |
| Credentials | `/opt/seafile/CREDENTIALS.txt` on the VPS (root-only, never in this repo) |
| GitHub | https://github.com/u2giants/seafile |

> **Current status (verified 2026-06-16):** VPS server, `nas-settings`, and the Synology `seaf-cli` container are running. The NAS container is healthy and the panel is receiving one status heartbeat per synced library from the current image; see [`docs/pending-work.md`](docs/pending-work.md) for current pending work.

## AI Sessions

Start with **`AGENTS.md`** in this repo root: it is the router to every document. The generated index is [`docs/INDEX.md`](docs/INDEX.md).

Shared infrastructure/NAS standards that apply beyond this repo live in [`u2giants/albert-standards`](https://github.com/u2giants/albert-standards): read [`infrastructure/seafile.md`](https://github.com/u2giants/albert-standards/blob/main/infrastructure/seafile.md) and [`synology/runbooks/seafile-sync-inotify.md`](https://github.com/u2giants/albert-standards/blob/main/synology/runbooks/seafile-sync-inotify.md) for infrastructure, server, NAS, or operating-environment changes. Update those standards in the same session when decisions here change the shared environment.
