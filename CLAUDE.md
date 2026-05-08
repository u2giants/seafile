# CLAUDE.md — Claude Code Instructions

Read **AGENTS.md** first. Everything substantive is there.

---

## Memory

Persistent memory path: `/home/ai/.claude/projects/-/memory/`

---

## Context

`.claudeignore` excludes nothing (this is a lean config-only repo with no large packages).

---

## Operations Permissions

Claude Code runs on the VPS (`172.233.14.233`) as `ai` (passwordless sudo). You may:
- Run Bash commands on this VPS directly
- Read/write files under `/home/ai/`, `/opt/seafile/` (with sudo), `/opt/seafile-data/` (with sudo)
- Use the `nas-direct` MCP server to run commands on edgesynology1
- Push to GitHub via `gh` (already authenticated as u2giants)

You may **not**:
- Make changes directly on the VPS or NAS and skip committing them to this repo
- Run `CONFIGURE_OAUTH.sh` or `CREATE_NAS_SYNC_ACCOUNT.sh` — these are one-time scripts already applied
- Enable the Cloudflare proxy on `seafile.designflow.app`

---

## Commit Style

- Short imperative subject line (`deploy seaf-cli-assets`, `fix caddy TLS config`)
- No ticket numbers or issue references needed
- Commit meaningful changes together — don't split a compose change from its doc update

---

## Tool Preferences

- Use Read/Edit/Write/Grep over bash equivalents for file operations
- Use `gh` CLI for GitHub operations
- Use the `nas-direct` MCP for all NAS interactions
- Credentials are in `/opt/seafile/CREDENTIALS.txt` (root-only — use sudo) and `/opt/seafile/.env`
