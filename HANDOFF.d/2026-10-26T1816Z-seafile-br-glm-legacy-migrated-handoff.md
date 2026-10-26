# HANDOFF

## 2026-10-26 session

Landed and verified:
- `sysadmin/sudo_mode.html` Microsoft SSO override: committed + merged (seafile#7, head `7d9d73b`), deployed live, template-load verified. Live rollback copy: `sudo_mode.html.bak-20261026` in the custom-templates dir.
- `albert-standards` Seafile reference + NAS inotify runbook published (albert-standards#4); this repo's links resolve.
- License incident (~1:35 PM EST): restart failed, "users exceeds limit, max 10, current 11" (two same-day SSO self-registrations). Duplicate no-profile account deactivated by session, then erased by Albert in the UI. Now exactly 10/10 active — the next added user blocks restarts until the license is upgraded. DB backup before the change: `/home/ai/seafile-db-backup-20261026.sql` (ai home, mode 600).

Unfinished — NAS memory-limit feature (started by an earlier session):
RESOLVED 2026-10-26 (later session): the feature landed and merged as seafile#11 —
stash `app.py` handler ported, six working-tree drafts reconciled, docker.sock
grant recorded in AGENTS.md Intentional quirks, reviewer final-check APPROVE.
The old `stash@{0}` snapshot and the incident note below are history only.
- License incident RECURRED ~2:17 PM EST the same day (Joao duplicate SSO account
  pushed users to 11; backend re-init failed, "server hiccup" 500s). Recovered the
  same way: backup `/home/ai/seafile-db-backup-20261026-incident2.sql`, deactivate
  duplicate, restart. Durable fix = license upgrade (owner decision).

Environment:
- GitHub auth on this VPS repaired (gh token restored from vps2). `ai-review` repaired: `/usr/local/bin/ai-review-pool` now symlinks to `/home/ai/ai-devops/bin/ai-review-pool` (was missing from the managed set).
- `.claude/worktrees/seafile-shared-folder-c0c2f0` belongs to a Claude Code session; untouched.
- Windows-workstation deployment was removed upstream (`ae8e1c9`); local edits to it were discarded in favor of upstream.

## Generic Decor / seaf-cli inotify recovery

Status:
partial

Done:
- Root cause verified: Generic Decor false-synchronized state was caused by Synology host inotify exhaustion, not a stale Seafile index.
- Live counts showed roughly 541k synced directories across the four worktrees, with about 444.7k @eaDir-related directories.
- Live library roots now have Seafile-recognized `seafile-ignore.txt` files with `@eaDir`, `#recycle`, `#snapshot`, `@tmp`, `.DS_Store`, `Thumbs.db`, and `*.tmp`.
- Mistaken live `.seafile-ignore` files were removed; Seafile does not recognize that filename.
- Repo code now writes/refreshes `seafile-ignore.txt` before the already-synced skip path, includes `#snapshot`, and tests this behavior.
- Watchdog design was changed away from filesystem signatures/restart-as-remedy toward commit-head verification, daemon log watch-error monitoring, inotify headroom, canary checks, and optional webhook alerts.
- Tests passed locally: `synology-seaf-cli/test_entrypoint.py` 35/35. Earlier nas-settings test passed 32/32 after dashboard/control updates.

Next action:
1. On `edgesynology1`, as root, raise host limits persistently with a DSM Task Scheduler boot-up task:
   `sysctl -w fs.inotify.max_user_watches=2097152`
   `sysctl -w fs.inotify.max_user_instances=1024`
2. Reboot or run the task, then verify:
   `sysctl fs.inotify.max_user_watches fs.inotify.max_user_instances`
3. Deploy the updated `seaf-cli` and `nas-settings` images after CI builds from this commit.
4. Restart/recreate `seaf-cli` after the host limit is raised, then verify no new `fail to add watch` / `No space left on device` entries appear in the daemon log.
5. Delete existing server-side `@eaDir` trees from Seafile only after confirming they are junk; the ignore file only prevents future uploads/changes.

Risks / watchouts:
- Do not use daemon restart as the repair; restart can mask the symptom with a one-time scan while leaving inotify broken.
- `seafile-ignore.txt` is cleanup/hygiene and may not reduce inotify watches because the monitor may still watch ignored directories.
- Synology continuously regenerates local `@eaDir` folders; seeing them reappear on the NAS is expected.
- The `ai` account could not run `sudo -n sysctl`; root/admin action is required for the host kernel limit and boot task.

## seaf-cli deployment migration to /volume1/docker/seaf-cli

Status:
done — migrated and verified on edgesynology1, 2026-06-21.

Done:
- `synology-seaf-cli/docker-compose.yml` is the source of truth: secrets via `env_file: - .env`, no shell-passthrough secret vars, `seaf-cli-data` `external: true`. `.env.example` + README (canonical deploy + 2026-06-21 incident) + AGENTS.md rule.
- `synology-monitor` `deploy/synology/docker-compose.agent.yml`: `seaf-cli` added to Watchtower's command.
- NAS migrated: stack now at `/volume1/docker/seaf-cli/` (`docker-compose.yml` + `.env`, chmod 600). Container force-recreated from the new dir; logs confirm creds auto-load (no `Bad configuration`) and all four libraries sync. Watchtower watch list verified `["synology-monitor-agent","synology-monitor-nas-api","seaf-cli"]`. Old `/volume1/homes/ahazan/seaf-cli-compose-codex.yml` + `seaf-cli.env` removed.

Remaining recurrence-prevention item (separate from the migration):
- Host `fs.inotify.max_user_watches` is live at 1048576 but NOT persisted (absent from `/etc/sysctl.conf` and `/etc/sysctl.d/`). A reboot resets it to 8192 and silently reintroduces the false-"synchronized" bug. Fix: a DSM Task Scheduler **boot-up** task (root) running `sysctl -w fs.inotify.max_user_watches=1048576` and `sysctl -w fs.inotify.max_user_instances=1024`. DSM boot task is required because Synology does not reliably honor `/etc/sysctl.conf` at boot / across DSM updates.

Watchouts:
- Never run `docker compose down -v` — it deletes the `seaf-cli-data` sync-state volume.
- Deploy seaf-cli ONLY from `/volume1/docker/seaf-cli/` with a `.env` present; never a home dir or `/tmp`, never shell-exported creds + `sudo` (sudo strips them → empty env → crash-loop, the 2026-06-21 outage).
