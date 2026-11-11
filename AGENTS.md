# AGENTS.md - POP Creations Seafile Infrastructure

The complete document index is [`docs/INDEX.md`](docs/INDEX.md), generated from document headers. Read it — or search it for your topic's keywords — before opening or searching any other document. Open a document only when its summary matches your task.

This file is the router: it routes, it does not contain. Reference detail lives in [`docs/agents-reference.md`](docs/agents-reference.md) (repository file map, modification inventory, task-to-file map, env table). Incidents live in [`docs/incidents.md`](docs/incidents.md), quirks in [`docs/idiosyncrasies.md`](docs/idiosyncrasies.md), pending work in [`docs/pending-work.md`](docs/pending-work.md), identifiers and containers in [`docs/identifiers.md`](docs/identifiers.md). New entries go to those files, never back here.

## Project summary

This repo operates POP Creations' Seafile Pro deployment at `seafile.designflow.app`: NYC Synology NAS design folders are uploaded by `seaf-cli` containers, stored in Linode Object Storage, and accessed by POP Creations staff through Seafile web/desktop clients. The important moving parts are the VPS Docker stack, the NAS sync containers, the `nas-settings` admin panel, Microsoft Entra SSO, and repo-driven CI images; the outcome that matters is reliable, auditable NAS-to-Seafile sync with safe admin controls.

## Multi-model AI note

There is no universal ignore-file standard across AI coding tools.

`.claudeignore` works for Claude Code.

When using any other AI tool, paste this file as your first message and follow the instructions in the "What to ignore" section.

## Standing rules (never skip)

- Branch policy: work on a feature branch and open a pull request; never push directly to `main`. Before the first commit run `git var GIT_COMMITTER_IDENT`; it must show `Albert Hazan <u2giants@users.noreply.github.com>`. Merge your own PR after checks pass.
- Workflow files are task class "deployment" for `ai-task-gates`; never pipe a gate check into a push.
- The `ai` account has no admin access on the NAS and it will not be restored (owner ruling 2026-10-26: "i'm not going to restore AI admin access on the NAS"). Stage file changes under `/volume1/docker/seaf-cli/`, hand the owner the exact command; routine image updates deploy themselves via Watchtower.
- Verify the live VPS before deploying: `hostname` must be `seafile-br` and `docker ps` must show the Seafile stack (see [deployment](docs/deployment.md)).
- Check license capacity and expiry before any planned `seafile` restart (see [incidents](docs/incidents.md) and [configuration](docs/configuration.md#effective-seafile-license)); all 12 seats are currently used.
- Never live-edit a server's installed upstream files; Seahub UI changes belong in `seafile-server/custom-templates/`.
- Shared standards live in [`albert-standards/infrastructure/seafile.md`](https://github.com/u2giants/albert-standards/blob/main/infrastructure/seafile.md) and [`albert-standards/synology/runbooks/seafile-sync-inotify.md`](https://github.com/u2giants/albert-standards/blob/main/synology/runbooks/seafile-sync-inotify.md); update them in the same session when operating-environment decisions change.
- Every new Markdown file gets the four-key header (`summary`, `kind`, `status`, `read-when`), then regenerate the index: `ai-doc-health --repo . --fix-index` (tool: [popcre/ai-devops](https://github.com/popcre/ai-devops), rules: `docs/doc-health.md` there). The index is never hand-edited.

## Documentation map: what to read for each task

Always start with:

- `AGENTS.md`
- [`docs/INDEX.md`](docs/INDEX.md) — the generated index of every document

Then load additional docs only when relevant:

| Task / question | Read these docs | Usually do not need |
|---|---|---|
| Quick repo orientation | `README.md`, `AGENTS.md` | Deep docs under `docs/` unless task requires them |
| Find a file, identifier, env var or edit target | `AGENTS.md`, [`docs/agents-reference.md`](docs/agents-reference.md), [`docs/identifiers.md`](docs/identifiers.md) | Other docs until a summary matches |
| Modify app behavior or project-owned code | `AGENTS.md`, relevant folder-level `README.md`, [`docs/architecture.md`](docs/architecture.md) if system design is affected | `docs/deployment.md` unless deploy behavior changes |
| Add or change configuration, env vars, secrets | `AGENTS.md`, `docs/configuration.md`, env table in `docs/agents-reference.md` | Deployment docs unless runtime env changes |
| Change local setup or debug workflow | `AGENTS.md`, [`docs/development.md`](docs/development.md) | `docs/deployment.md` unless CI/CD changes |
| Change deployment, Docker, CI/CD, rollback | `AGENTS.md`, `docs/deployment.md`, `docs/configuration.md` | Local-only development docs |
| Investigate bugs or incidents | `AGENTS.md`, `docs/incidents.md`, `docs/idiosyncrasies.md`, docs for the affected area, `HANDOFF.md` if present | Unrelated folder READMEs |
| Continue unfinished work | `AGENTS.md`, `HANDOFF.md` → open files in `HANDOFF.d/`, docs named inside them | Docs unrelated to the handoff scope |
| Work in a subfolder with its own README | `AGENTS.md`, that folder-level `README.md` | Other folder-level READMEs |
| Claude Code session | `CLAUDE.md`, then `AGENTS.md` | Other docs unless task requires them |
| Documentation-only cleanup | `AGENTS.md`, `README.md`, affected docs, `docs/INDEX.md` rules above | Source files except as needed to verify accuracy |

`HANDOFF.md` is required reading when it exists. It is a temporary pointer to `HANDOFF.d/`, not canonical architecture. [`docs/plan-license-recovery-2026-11.md`](docs/plan-license-recovery-2026-11.md) records the completed November 2026 license recovery: read its STATUS first and do not repeat its historical replacement steps. Current license capacity is 12 users, expiring October 26, 2027 (installed November 9, 2026). Runtime credential references are in [`docs/1password.md`](docs/1password.md); do not restore private literals into public operating notes.

## Prime Directive: custom-code boundary

Our custom code lives here:

- `seafile-server/nas-settings/`
- `synology-seaf-cli/`
- `seafile-server/custom-templates/`
- `seafile-server/*.yml`
- `seafile-server/*.sh`
- `docs/`
- folder-level `README.md` files
- `.github/workflows/`

Everything else requires justification before touching. Do not edit Seafile's installed upstream files inside containers as the production change. Seahub UI changes belong in `seafile-server/custom-templates/`; runtime config changes must be documented and backed up. The full repository structure and modification inventory are in [`docs/agents-reference.md`](docs/agents-reference.md).

## What to ignore

Do not spend AI context on:

- `.git/`
- `__pycache__/`
- `*.pyc`
- `.env`
- `CREDENTIALS.txt`
- `*.sql`
- `.cache/`
- `coverage/`
- `dist/`
- `node_modules/`
- `.ai/reviews/`
- Build artifacts or generated output if any appear later
- [`docs/lucid-storage-strategy.md`](docs/lucid-storage-strategy.md) unless the task is specifically about storage-strategy research

`.claudeignore` and `.cursorignore` must match this section where path ignores apply. `.copilotignore` is absent because this repo has no Copilot-specific ignore need documented.

## Credentials and environment

Never commit actual secret values. The full variable-by-variable table (purpose, where stored, dev/prod need) is the "Credentials and environment" section of [`docs/agents-reference.md`](docs/agents-reference.md); live values and per-file detail are in [`docs/configuration.md`](docs/configuration.md) and [`docs/1password.md`](docs/1password.md). Other secret material lives in `/opt/seafile/CREDENTIALS.txt` on the VPS, root-only. Do not paste or commit it.

## Deployment

Real deployment path (details and commands in [`docs/deployment.md`](docs/deployment.md)):

- Branch: `main` via pull request; CI workflows `seaf-cli image` and `nas-settings image` run tests (pyflakes + Python tests) and publish `ghcr.io/u2giants/seafile:seaf-cli-latest` / `nas-settings-latest` plus `sha-<commit>` tags.
- Deploy trigger: manual pull/recreate on the target host after CI succeeds. There is no Coolify, deploy webhook, or app/project ID.
- VPS stack: Docker Compose from `/opt/seafile` plus repo files in `/home/ai/seafile-repo/seafile-server/`; `nas-settings` deploys with `--env-file /opt/seafile/.env` and is never built on the VPS.
- NAS deploy: stage under `/volume1/docker/seaf-cli/` and hand the owner the exact command (no AI admin access on the NAS).
- Rollback: pin the affected service image to an older immutable `sha-<commit>` tag and recreate.
- GitHub Actions must not SSH to production or run Docker there.

<!-- ansible-host-policy: managed rollout from u2giants/ansible -->
## Host / server changes — do NOT make them here

The `hetz` server's host/OS layer is managed by **Ansible** in **[`u2giants/ansible`](https://github.com/u2giants/ansible)**. To change the server (packages, users, firewall, DNS, Docker *engine* config, system cron, systemd units, Cloudflare Tunnel 1, the backup watchdog), **open a PR there** and let CI apply it — **never** SSH into the box and hand-edit it. Manual changes are drift and get reverted by the next apply. See [`u2giants/ansible/AGENTS.md`](https://github.com/u2giants/ansible/blob/main/AGENTS.md).

This repo is **not** the host layer. Its own changes belong here and deploy through their normal pipeline. Don't put host-level changes here, and don't manage this service's container with Ansible. Scope boundary: **Ansible owns the host; this repo owns the Seafile application stack.**
