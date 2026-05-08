# Handoff

Delete this file when designer accounts are confirmed set up.

## What Is Fully Done

- Seafile Pro 13.0 running on Linode VPS (172.233.14.233) at seafile.designflow.app
- TLS, Google OAuth SSO, S3 storage (Linode br-gru-1) all live
- NAS sync account: nas-sync@popcre.com
- `seaf-cli-char-licensed` — syncing `/volume1/mac/Decor/Character Licensed` → Character Licensed library ✅
- `seaf-cli-generic-decor` — syncing `/volume1/mac/Decor/Generic Decor` → Generic Decor library ✅
- Daily MySQL backup cron, Docker auto-start on boot

## Remaining

- Designer accounts (8 São Paulo designers): send them https://seafile.designflow.app, they sign in with Google SSO, accounts auto-create. Then share Character Licensed and Generic Decor libraries with each (Read/Write).
