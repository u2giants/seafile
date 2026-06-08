# HANDOFF

Last updated: 2026-06-08. Read `AGENTS.md` first, then this file for live in-flight state.
Delete this file once the pause/resume fix is verified on the NAS **and** the 8 designers are onboarded.

---

## Scope of recent work (2026-06-07 / 08)

Built a full **seaf-cli control GUI** inside the Seafile web UI (the `nas-settings` panel) and hardened the
surrounding auth/deploy. All code is committed and pushed to `main`; both CI workflows are green.

### Fully done (committed + deployed)
- **nas-settings control panel** — tabs Dashboard / Controls / Config / Libraries / Ingest Window, driven by a
  UUID-routed poll + command-queue bridge (`/api/command` → container picks it up on its 30 s `/api/status` poll →
  reports result). Server code: `seafile-server/nas-settings/app.py` + `templates/`. NAS side: dispatcher in
  `synology-seaf-cli/entrypoint.py`. **Live on the VPS** (image `ghcr.io/u2giants/seafile:nas-settings-latest`).
- **nas-settings now CI-built + published** (`.github/workflows/nas-settings-image.yml`); `nas-settings.yml`
  pulls the published image (no local build). Deployed + cut over on the VPS.
- **Admin-check fix** — `SEAFILE_INTERNAL_URL=http://seafile` (nginx :80, not Seahub's localhost :8000). Deployed.
- **Main-app sidebar link** — `seafile-server/custom-templates/react_app.html` (admin-only "NAS Sync" link).
  Copied into the Seahub custom dir + `docker restart seafile`; template override is active.
- **SSO binding + duplicate cleanup** — re-pointed `albert@popcre.com → 4cba…` (admin); deleted the duplicate
  non-admin accounts. Set `login_id=albert` on the admin account. Runtime state only — not in the repo.
- **Tests** — `seafile-server/nas-settings/test_app.py`, `synology-seaf-cli/test_entrypoint.py`, both in CI.

### Partially done / exact current state
- **Pause/resume fix is NOT yet live on the NAS.** The fix (per-repo `auto-sync` property; commit `d3fc09f`) is
  built and published as `:seaf-cli-latest`, but the **running** containers on edgesynology1 predate it. They
  must be recreated to pick it up. The NAS MCP cannot run `docker compose`/`start`, so this is an SSH step on
  edgesynology1, and `/tmp` is wiped on reboot so the compose + `.env` need re-staging first.
- **Break-glass password** — `login_id=albert` is set, but Albert still needs to set the password
  (System Admin → Users → `4cba…@auth.local` → Reset Password) and test `albert` + password at `/accounts/login/`.

### Not started
- **Onboard 8 São Paulo designers** — send `https://seafile.designflow.app`; they sign in with M365 SSO
  (accounts auto-create), then share Character Licensed + Generic Decor at Read/Write.

---

## Exact next action

On **edgesynology1** (the NYC NAS — *not* the VPS `seafile-br`, *not* edgesynology2), recreate both containers
on the latest image. The self-contained block (stages compose + reads creds from the running container's env, so
no secrets are typed) is in `synology-seaf-cli/README.md` → "Updating the image" / the deploy block. Then in the
panel click **Pause** on a library and confirm it flips to **Paused** within ~30–40 s (that round-trip is the fix).

---

## Decisions made, and why
- **Fixed the SSO binding instead of the OAuth config remap** — investigation showed Microsoft *was* sending the
  `email` claim; the binding had just been re-pointed to a duplicate. Re-pointing it (low risk) was correct; the
  `sub`-based config remap (riskier, orphans bindings) was deliberately *not* done. Optional follow-up if dups recur.
- **nas-settings → CI build + publish** — to satisfy the CI/CD rules (production images must be CI-built and
  traceable); local VPS builds were the prior, non-compliant path.
- **Pause via per-repo `auto-sync` property** — the seaf-cli 7.0.10 RpcClient has no global auto-sync toggle
  (verified by introspecting the image); `set_repo_property(repo_id, "auto-sync", "false"/"true")` is the mechanism.

## Known risks / unknowns
- The NAS deploy relies on `/tmp` (wiped on reboot). Optional Pending Work: move compose/`.env` to a persistent
  path (`/volume1/docker/seaf-cli/`).
- Until the NAS recreate happens, Pause/Resume in the panel will queue but the old image can't execute the new
  per-repo logic — so they appear to "not work." That's expected pre-recreate.
