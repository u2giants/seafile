---
summary: Critical incident write-ups: removed NAS containers, SSO duplicate admin binding, panel redirect, OAuth cleanup, license-cap restart outages.
kind: living
status: current
read-when: debugging a familiar symptom before re-investigating
---

Critical incidents, moved out of AGENTS.md on 2026-11-11. Each write-up records what happened, impact, root cause, recovery, and the rule added to prevent recurrence. New incidents go here, never back into AGENTS.md.


### 2026-06-05 NAS seaf-cli containers found removed

What happened:
The NAS sync containers were absent from `docker ps -a`, so sync had silently stopped.

Impact:
NAS-to-Seafile uploads were not running. No data loss was documented; Seafile libraries, S3 data, and Docker volumes remained.

Root cause:
Unknown. Docker event history did not retain the removal event. Possible manual removal, Synology Container Manager behavior, or NAS maintenance.

Recovery:
Containers were recreated from `synology-seaf-cli/docker-compose.yml`.

Rule added to prevent recurrence:
Verify live container state before documenting sync status; do not trust stale status claims in docs.

### 2026-06-07 SSO admin binding pointed at a duplicate account

What happened:
Microsoft SSO for `albert@popcre.com` landed on a non-admin duplicate account instead of the real admin.

Impact:
The NAS Settings panel and admin-only sidebar link appeared missing because the session was non-admin.

Root cause:
OAuth binding/account churn in `seahub_db.social_auth_usersocialauth`.

Recovery:
The binding was repointed to the admin account and duplicate active users were removed. Current active users are the SSO admin and `nas-sync` machine account.

Rule added to prevent recurrence:
If an SSO duplicate appears, fix the binding and account ownership rather than promoting the duplicate. Verify `EmailUser`, `profile_profile`, and `social_auth_usersocialauth` together.

### 2026-06-07 nas-settings redirected admins because internal URL used Seahub `:8000`

What happened:
Admins visiting `/nas-settings/` were redirected away because the panel's admin-session check could not reach Seahub at `http://seafile:8000`.

Impact:
The panel was unusable even for admins.

Root cause:
Seahub gunicorn binds localhost inside the Seafile container; other containers must reach it through nginx on port 80.

Recovery:
`SEAFILE_INTERNAL_URL` was changed to `http://seafile`.

Rule added to prevent recurrence:
Use the Seafile container's nginx port 80 for internal panel admin checks, not Seahub's localhost-only port 8000.

### 2026-06-08/09 Microsoft OAuth and account cleanup

What happened:
The generic/no-prompt SSO behavior and later duplicate SSO account state required live Seahub config and database cleanup.

Impact:
Incorrect SSO behavior risked insecure login flow or admin landing on the wrong account.

Root cause:
Stale/misconfigured SSO settings and duplicate OAuth bindings/accounts.

Recovery:
Configured Microsoft Entra OAuth, preserved secrets out of output, transferred NAS library ownership to the SSO admin, kept `nas-sync` as the machine account, removed obsolete active users, and made the two NAS libraries internally visible read-only.

Rule added to prevent recurrence:
Back up DB/config before destructive account or ownership changes; keep secrets out of output; document account identities by internal username plus contact email.

### 2026-10-26 Seafile restart failed: user count over license cap

What happened:
Deploying the landed `sudo_mode.html` override required `docker restart seafile`; startup failed with `users exceeds limit, max 10, current 11` and the public site returned 502.

Impact:
Full outage (~40 minutes). Cause was NOT the template: two Microsoft SSO self-registrations the same afternoon had pushed active users to 11, one over the Seafile Pro free-tier cap; the check only runs at startup.

Recovery:
Backed up `ccnet_db`/`seahub_db`, deactivated the duplicate no-profile account, restarted cleanly. Albert then erased that duplicate in the UI. Backup kept at `/home/ai/seafile-db-backup-20261026.sql` on the VPS.

Rule added to prevent recurrence:
Before any planned `seafile` container restart, compare the active `ccnet_db.EmailUser` count with `MaxUsers` in the effective `/opt/seafile-data/seafile/seafile-license.txt` and verify its expiration. Never assume the historical 10-user ceiling still applies. On November 5, 2026, the owner supplied an 11-user replacement expiring October 26, 2027; installation and live proof are tracked on issue #19. Ten staff plus the NAS sync account require all eleven seats; another account needs additional capacity first.

Recurrence (2026-11-09): onboarding Claudia Cadena (ccadena@popcre.com) on November 5 made 12 accounts; the next restart failed with `users exceeds limit, max 11, current 12` and the site showed "Error, please contact administrator." The owner supplied a 12-user license (same expiry); it was installed (previous file kept as `seafile-license.txt.bak-20261109-11user`) and Seafile restarted cleanly. All 12 seats (11 staff + NAS sync) are now used: buy capacity before onboarding anyone else.

Recurrence (same day, ~2:17 PM EST): a SECOND account for Joao Melhorance (`8ed31406…@auth.local`) appeared and pushed the count to 11; the backend's internal re-init failed user-manager setup, killing the RPC pipe while gunicorn kept serving — logged-in users saw Seahub's "server hiccup" 500 page instead of a 502. Same recovery: DB backup (`/home/ai/seafile-db-backup-20261026-incident2.sql`), deactivate the duplicate, restart, verified all-API-200.

Root cause (fixed ~4:15 PM EST): Joao's profile (`089e556d…@auth.local`, jmelho@popcre.com) had been pre-created ~12:24 PM EST without an SSO link. Seahub's OAuth login matches by `(provider, uid)` link, then by a login-identifier lookup of the Microsoft email claim — it never checks `profile.contact_email`, so his sign-in found nothing and auto-created a new account. Fix applied, no license change (owner ruling: fix the problem): moved his `designflow.app` binding to his real profile, deleted the empty duplicate via admin API (exactly 10 users again), and set `REMOTE_USER_CREATE_UNKNOWN_USER = False` in live `seahub_settings.py` (backup: `seahub_settings.py.bak-20261026-dupfix`) so an unknown identity now gets "registration is not allowed" instead of silently creating user 11. Onboarding procedure from now on: pre-create in the admin UI, then add the `social_auth_usersocialauth` link for the user's Microsoft identity before their first sign-in.

## 2026-11-12 — Seat-limit outage again (14 users vs 12-user license)

Two SSO users (asilva, lherrera) were auto-created on 2026-11-11 despite the 2026-10-26 guard, because `REMOTE_USER_CREATE_UNKNOWN_USER` is not read by the OAuth backend (`seahub/oauth/backends.py` reads `OAUTH_CREATE_UNKNOWN_USER`). On restart seaf-server failed "number of users exceeds limit, max 12, current 14". Fix: deactivated the two newest accounts (reversible), added `OAUTH_CREATE_UNKNOWN_USER = False` and `OAUTH_ACTIVATE_USER_AFTER_CREATION = False` to live `seahub_settings.py` (backup kept), restarted, verified login page 200 and no limit error. Reactivating them needs 2 more seats or removing two others.
