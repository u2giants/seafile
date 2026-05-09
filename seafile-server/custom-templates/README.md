# custom-templates

Django template overrides for Seahub. Files here are deployed to `/opt/seafile-data/seafile/seahub-data/custom/templates/` on the VPS, which Seafile loads before its own built-in templates.

## Current overrides

### `sysadmin/sysadmin_react_app.html`

A verbatim copy of Seafile's built-in `sysadmin/sysadmin_react_app.html` with one addition: a MutationObserver script injected after the `sysAdmin` React bundle that appends a "NAS Sync Settings" link to the System Admin sidebar nav.

**Why a full copy instead of a partial override:** Django template inheritance is single-level — a template in the custom directory cannot `{% extends %}` the Seafile template it overrides. The full copy was necessary.

**Upgrade risk:** If Seafile is upgraded and the upstream template changes, this copy will not automatically receive those changes. After any Seafile upgrade, diff this file against the new upstream at `/opt/seafile/seafile-pro-server-<version>/seahub/seahub/templates/sysadmin/sysadmin_react_app.html` inside the container and merge as needed.

## Deployment

Files in this directory must be manually copied to the VPS after changes:

```bash
sudo cp seafile-server/custom-templates/sysadmin/sysadmin_react_app.html \
  /opt/seafile-data/seafile/seahub-data/custom/templates/sysadmin/sysadmin_react_app.html
docker restart seafile
```
