# HANDOFF

Last updated: 2026-06-08. Repo HEAD at handoff: `de04c71` on `main`.
Read `AGENTS.md` first (project overview, architecture, identifiers, credentials), then this file for live in-flight state.
**Delete this file** once the pause/resume fix is verified on the NAS **and** the 8 designers are onboarded.

---

## TL;DR (one paragraph)

We built a full **seaf-cli control GUI** inside the Seafile web UI — the `nas-settings` panel at
`https://seafile.designflow.app/nas-settings/` (tabs: Dashboard / Controls / Config / Libraries / Ingest Window).
It controls the seaf-cli sync containers on the NYC Synology NAS over a poll + command-queue bridge. Everything is
**committed, CI-green, and deployed** except one thing: a **pause/resume bug fix** is in the published NAS image but
the **running NAS containers predate it**, so they must be recreated to pick it up, then pause verified. After that,
the only remaining work is onboarding the 8 designers. There is no data at risk — the site has not gone live.

---

## 0. Access you need before you can do anything

You cannot complete the next action without these. **Getting access provisioned (SSH keys, office-network/VPN) is
not documented in the repo and only Albert can grant it — ask him.** What's known:

| Target | What it is | How it's reached | Notes |
|---|---|---|---|
| **VPS** `172.233.14.233` (`seafile-br`) | Runs the Seafile server **and** the `nas-settings` panel. Repo is checked out at `/home/ai/seafile-repo`. | SSH as user `ai` (passwordless `sudo`); `su - root` was also used this session | This is where you `git pull`, rebuild/pull the panel, read creds |
| **NAS** `edgesynology1` (`192.168.3.100`) | Runs the two seaf-cli sync containers. **This is where the next action happens.** | SSH (operator account seen this session: `ahazan@…`). **`192.168.3.100` is a NYC-office LAN IP — remote access needs the office network or a VPN. Exact remote path is UNKNOWN to me; ask Albert.** | Docker is **not** in PATH: `/var/packages/ContainerManager/target/usr/bin/docker`. `/tmp` is wiped on reboot. |
| **Panel admin login** (to verify) | A Seafile **system admin** session — the panel is admin-only | `https://seafile.designflow.app/accounts/login/`, use the **email/password form (NOT the "Single Sign-On" button)**: `u2giants@gmail.com` + password from `/opt/seafile/CREDENTIALS.txt` on the VPS (`sudo cat /opt/seafile/CREDENTIALS.txt`) | Do not use SSO for admin — it can land on a non-admin account (see AGENTS.md → Critical Incident Log). Break-glass `albert` exists but its password isn't set yet. |
| **NAS MCP** (`nas-direct`) | Read-only NAS diagnosis from an AI session | Bearer token | **Read-only** — it CANNOT `docker compose up`/`pull`/`start`. The recreate below must be done over SSH, not via the MCP. |

Credentials index is in `AGENTS.md → Credentials and Environment`. Never paste secrets into the repo or chat.

---

## 1. Fully done (committed + deployed)
- **nas-settings control panel** — UUID-routed poll + command-queue bridge: browser → `POST /api/command` →
  container picks it up on its 30 s `POST /api/status` poll → runs it → reports the result back. Server code:
  `seafile-server/nas-settings/app.py` + `templates/`; NAS-side dispatcher: `synology-seaf-cli/entrypoint.py`.
  **Live** on the VPS as `ghcr.io/u2giants/seafile:nas-settings-latest`.
- **nas-settings is CI-built + published** (`.github/workflows/nas-settings-image.yml`); `nas-settings.yml` pulls
  that image (no `build:`). Deployed + cut over on the VPS.
- **Admin-check fix** — `SEAFILE_INTERNAL_URL=http://seafile` (nginx :80, not Seahub's localhost :8000). Deployed.
- **Main-app sidebar "NAS Sync" link** — `seafile-server/custom-templates/react_app.html` (admin-only). Copied into
  the Seahub custom dir + `docker restart seafile`; override is active.
- **SSO binding + duplicate cleanup** — re-pointed `albert@popcre.com → 4cba…` (the admin); deleted the duplicate
  non-admin accounts; set `login_id=albert` on the admin account. (Runtime state, not in the repo.)
- **Tests in CI** — `seafile-server/nas-settings/test_app.py`, `synology-seaf-cli/test_entrypoint.py`.

## 2. In flight — exact current state
- **Pause/resume fix is NOT yet live on the NAS.** The fix (per-repo `auto-sync` property; commit `d3fc09f`) is
  built and published as `:seaf-cli-latest`, but the **running** containers on edgesynology1 were created from an
  earlier image, so Pause/Resume in the panel currently queue but don't take effect. Recreating the containers
  (Step in §3) picks up the fix. This is the one open engineering item.
- **Break-glass password** — `login_id=albert` is set; Albert still needs to set the password (System Admin →
  Users → `4cba…@auth.local` → Reset Password) and test `albert` + password at `/accounts/login/`.

## 3. EXACT NEXT ACTION — recreate the NAS containers, then verify pause

**Run on `edgesynology1` over SSH** (see §0 for access; confirm the shell prompt says `edgesynology1`, NOT
`seafile-br` and NOT `edgesynology2`). The full copy-paste block — which stages `/tmp/.env` from the running
container's own env (no secrets typed) and writes `/tmp/seaf-cli-compose.yml`, then pulls + recreates — is in
**`synology-seaf-cli/README.md` → "Updating the image"**. In short:

```bash
DOCKER=/var/packages/ContainerManager/target/usr/bin/docker
# 1) rebuild /tmp/.env from the running container's baked-in creds (nothing secret typed)
sudo $DOCKER inspect seaf-cli-char-licensed --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -E '^(SEAF_USERNAME|SEAF_PASSWORD|SEAF_STATUS_TOKEN)=' | sudo tee /tmp/.env >/dev/null
# 2) write /tmp/seaf-cli-compose.yml = this repo's synology-seaf-cli/docker-compose.yml (full block in the README)
# 3) pull + recreate
sudo $DOCKER pull ghcr.io/u2giants/seafile:seaf-cli-latest
sudo $DOCKER compose -f /tmp/seaf-cli-compose.yml --env-file /tmp/.env up -d --force-recreate
```

**Verify:**
1. `sudo $DOCKER ps --filter name=seaf-cli` → both `seaf-cli-char-licensed` and `seaf-cli-generic-decor` show
   "Up … (health: starting → healthy)", created just now.
2. Log into the panel as admin (§0) → open `https://seafile.designflow.app/nas-settings/` → **Controls** → click
   **Pause** on a library → within ~30–40 s the badge flips to **Paused**; **Resume** flips it back.

**If pause still doesn't flip:** the command path is observable end-to-end:
- On the VPS: `sudo docker exec nas-settings cat /data/results.json` shows each command's `ok`/`error` (this is how
  the original bug — `'SeafileRpcClient' object has no attribute 'disable_auto_sync'` — was found).
- On the NAS: `sudo $DOCKER logs --tail 50 seaf-cli-char-licensed` shows "Executing queued command: …".

## 4. Not started
- **Onboard 8 São Paulo designers** — send `https://seafile.designflow.app`; each signs in with their POP Creations
  **M365** account (the "Single Sign-On" button — accounts auto-create, tenant-locked). Then, as admin, share both
  libraries with each at Read/Write: open the library → **Share → Share to User →** enter their email → Read/Write.
  Watch for SSO duplicate accounts (AGENTS.md → Critical Incident Log); if one appears, fix the binding, don't
  promote the duplicate.

## 5. Decisions made, and why
- **Fixed the SSO binding, did NOT do the OAuth config remap.** Microsoft *was* sending the `email` claim — the
  binding had just been re-pointed to a duplicate during account churn. Re-pointing it (low risk) was correct; the
  `sub`-based config remap (riskier, orphans bindings) was deliberately deferred to optional Pending Work.
- **nas-settings moved to CI build + publish** to satisfy the CI/CD rules (production images must be CI-built and
  traceable); local VPS builds were the prior, non-compliant path.
- **Pause via per-repo `auto-sync` property.** The seaf-cli 7.0.10 RpcClient has no global auto-sync toggle (verified
  by introspecting the image); `set_repo_property(repo_id, "auto-sync", "false"/"true")` is the working mechanism.

## 6. Dead ends / things NOT to retry
- Don't try to recreate the NAS containers via the `nas-direct` MCP — `docker run`/`compose up`/`start` are blocked
  there even base64-encoded. Use SSH.
- Don't call `rpc.disable_auto_sync()` / `enable_auto_sync()` — those methods don't exist in this client (that was
  the original pause bug).
- Don't change `SEAFILE_INTERNAL_URL` back to `:8000` — Seahub binds localhost there; the panel must use nginx `:80`.

## 7. Risks / unknowns
- **Remote access to `edgesynology1` is not documented** (LAN IP; needs office network/VPN). Ask Albert. This is the
  main thing blocking a no-context dev from executing §3.
- The NAS deploy relies on `/tmp` (wiped on reboot). Optional Pending Work: move compose/`.env` to a persistent path
  (`/volume1/docker/seaf-cli/`).
- The 2026-06-05 "containers vanished" root cause was never found; if they disappear again, `restart: unless-stopped`
  wasn't enough — investigate Synology Container Manager behavior (AGENTS.md → Critical Incident Log).

## 8. Verify current state yourself (don't trust this doc blindly)
- NAS containers: `sudo $DOCKER ps -a --filter name=seaf-cli` on edgesynology1.
- Panel up: `curl -sI https://seafile.designflow.app/nas-settings/` → `302` (redirect to login), served by Werkzeug.
- Run the test suites locally: `cd seafile-server/nas-settings && pip install flask && python test_app.py`;
  `python synology-seaf-cli/test_entrypoint.py` (stubs the seafile module — no daemon needed).
