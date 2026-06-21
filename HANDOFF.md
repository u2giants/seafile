# HANDOFF

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
partial (repo done; NAS migration is a one-time operator action)

Done:
- `synology-seaf-cli/docker-compose.yml` updated to be the source of truth: loads secrets via `env_file: - .env`, drops shell-passthrough secret vars, marks `seaf-cli-data` `external: true`. `.env.example` corrected. README rewritten with canonical deploy + the 2026-06-21 incident.
- `synology-monitor` `deploy/synology/docker-compose.agent.yml`: `seaf-cli` added to Watchtower's watch list.

Next action (operator, on edgesynology1 — one time):
1. Create `/volume1/docker/seaf-cli/`, put this repo's `synology-seaf-cli/docker-compose.yml` there, and move the existing creds file to `/volume1/docker/seaf-cli/.env` (`chmod 600`).
2. `cd /volume1/docker/seaf-cli && sudo docker compose down` is NOT needed; `sudo docker compose up -d` recreates the `seaf-cli` project in place. Then remove the old home-dir files (`/volume1/homes/ahazan/seaf-cli-compose-codex.yml`, `seaf-cli.env`).
3. Apply the Watchtower change: `cd /volume1/docker/synology-monitor-agent && sudo docker compose -f compose.yaml up -d`.

Risks / watchouts:
- Never run `docker compose down -v` — it would delete the `seaf-cli-data` sync-state volume.
- Deploy ONLY from `/volume1/docker/seaf-cli/` with a `.env` present; never from a home dir or `/tmp`, never via shell-exported creds + `sudo` (sudo strips them → empty env → crash-loop). This was the 2026-06-21 outage.
