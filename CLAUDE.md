# CLAUDE.md — Claude Code Instructions

Read **AGENTS.md** first. Everything substantive is there.

---

## Memory

Persistent memory path: `/home/ai/.claude/projects/-/memory/`

---

## Context

Use `.claudeignore` for context economy. It mirrors `.cursorignore`; both are aligned with `AGENTS.md` → What to ignore.

---

## Branch & deployment model

- **`main` only.** Commit straight to `main` — no feature branches, no PRs.
- **CI publishes; it does not deploy.** `.github/workflows/seaf-cli-image.yml` and `nas-settings-image.yml` lint, test, build, and push their images to GHCR. Deployment is a separate manual, repo-driven pull on the target host.
- **SSH is NOT a CI deployment path.** GitHub Actions must never SSH into the VPS/NAS or run Docker there. Claude runs *on* the VPS and may run host commands for manual ops/debugging. NAS container recreates are manual operator SSH work on `edgesynology1`, not NAS MCP work. Production behavior must always be defined by repo files + published images.
- GitHub Secrets hold no deploy/SSH keys — CI uses only `GITHUB_TOKEN`.

---

## Operations Permissions

Claude Code runs on the VPS (`172.233.14.233`) as `ai` (passwordless sudo). You may:
- Run Bash commands on this VPS directly
- Read/write files under `/home/ai/`, `/opt/seafile/` (with sudo), `/opt/seafile-data/` (with sudo)
- Use the `nas-direct` MCP server only if it is available and only for read-only diagnosis on edgesynology1. Base64-encode any read-only docker command because the MCP allowlist blocks the literal string "docker".
- Push to GitHub via `gh` (already authenticated as u2giants)

You may **not**:
- Make changes directly on the VPS or NAS and skip committing them to this repo
- Run `CONFIGURE_OAUTH.sh` or `CREATE_NAS_SYNC_ACCOUNT.sh` — these are one-time scripts already applied
- Enable the Cloudflare proxy on `seafile.designflow.app`

---

## Commit Style

- Short imperative subject line (`fix caddy TLS config`, `add nas-settings panel`)
- No ticket numbers or issue references needed
- Commit meaningful changes together — don't split a compose change from its doc update

---

## Tool Preferences

- Use Read/Edit/Write/Grep over bash equivalents for file operations
- Use `gh` CLI for GitHub operations
- Use SSH, not `nas-direct`, for NAS deploy/recreate work
- Credentials are in `/opt/seafile/CREDENTIALS.txt` (root-only — use sudo) and `/opt/seafile/.env`
