---
summary: Seahub template overrides (Microsoft login button, admin sidebar links, sudo mode) deployed to the custom templates dir; re-diff after every Seafile upgrade.
kind: living
status: current
read-when: changing login branding or sidebar links
---

# custom-templates

Django template overrides for Seahub. Files here are deployed to `/opt/seafile-data/seafile/seahub-data/custom/templates/` on the VPS, which Seafile loads before its own built-in templates.

## Current overrides

### `sysadmin/sysadmin_react_app.html`

A verbatim copy of Seafile's built-in `sysadmin/sysadmin_react_app.html` with one addition: a MutationObserver script injected after the `sysAdmin` React bundle that appends a "NAS Sync Settings" link to the System Admin sidebar nav.

**Why a full copy instead of a partial override:** Django template inheritance is single-level — a template in the custom directory cannot `{% extends %}` the Seafile template it overrides. The full copy was necessary.

**Upgrade risk:** If Seafile is upgraded and the upstream template changes, this copy will not automatically receive those changes. Before any Seafile upgrade, compare this file with the new release's upstream copy (step 3 of [Seafile server updates](../../docs/deployment.md#seafile-server-updates-same-130-line)) and merge as needed.

### `react_app.html`

A verbatim copy of Seafile's built-in `react_app.html` (the main workspace app) with one addition: an **admin-only** (`{% if user.is_staff %}`) MutationObserver script that appends a "NAS Sync" link to the main left sidebar (`.side-nav-con .nav-container`), pointing at `/nas-settings/`. So admins can reach the panel from the normal Seafile UI without typing the URL; non-admin designers don't see a link they can't use.

Same full-copy rationale and upgrade risk as above — re-diff against `/opt/seafile/seafile-pro-server-<version>/seahub/seahub/templates/react_app.html` before a Seafile upgrade. (Upstream baseline: 13.0.21. The 13.0.30 upstream files were compared with it on 2026-11-23 and are byte-identical for all four overrides; the comparison snippet under [Seafile server updates](../../docs/deployment.md#seafile-server-updates-same-130-line) re-checks it.)

### `sysadmin/sudo_mode.html`

A copy of Seafile's built-in admin sudo-mode template adjusted for the POP Creations Microsoft SSO deployment. The stock template asks admins to confirm a local password and its SSO button targets Shibboleth/ADFS. This override makes "Sign in with Microsoft" the primary action and sends admins through Seafile's existing `{% url 'sso' %}` route, preserving the `next` admin URL. Seafile already refreshes sudo-mode after a staff OAuth login, so no Python patch is required.

The local password form remains available behind a disclosure for emergency/local admin accounts.

### `registration/login.html`

A verbatim copy of Seafile's built-in login template with one visual change: the SSO button renders as a Microsoft-branded "Sign in with Microsoft" button. The existing `#sso` click handler and Seahub SSO/OAuth route are unchanged.

**Validate before activating** (templates are cached, so a copy has no effect until Seahub reloads — and a syntax error would break the page for everyone once it does). Compile it in Seahub's own environment first:

```bash
docker exec seafile bash -lc '
cd /opt/seafile/seafile-pro-server-*/seahub
PID=$(pgrep -f "wsgi:application" | head -1)
while IFS= read -r -d "" l; do export "$l"; done < /proc/$PID/environ
python3 -c "import django; django.setup(); from django.template.loader import get_template; get_template(\"react_app.html\"); print(\"OK\")"'
```

Replace `react_app.html` with the template you changed when validating a specific override.

## Deployment

Files in this directory must be manually copied to the VPS, then Seahub restarted (templates are cached, so changes do not take effect until then):

```bash
DST=/opt/seafile-data/seafile/seahub-data/custom/templates
sudo cp seafile-server/custom-templates/sysadmin/sysadmin_react_app.html "$DST/sysadmin/sysadmin_react_app.html"
sudo cp seafile-server/custom-templates/sysadmin/sudo_mode.html          "$DST/sysadmin/sudo_mode.html"
sudo cp seafile-server/custom-templates/react_app.html                   "$DST/react_app.html"
sudo mkdir -p "$DST/registration"
sudo cp seafile-server/custom-templates/registration/login.html          "$DST/registration/login.html"
docker restart seafile   # ~30-90s full blip (web + sync). Validate the template first (above).
```

All four deployed copies must stay byte-identical to this directory (`sudo cmp` each pair; `sudo_mode.html` on the VPS is root-only).

To roll back a bad override: delete the file from `$DST` and `docker restart seafile` — Seahub falls back to its built-in template.
