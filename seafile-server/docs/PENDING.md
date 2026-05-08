# Pending Work

These are the remaining tasks to fully complete the deployment. Each section explains what needs to happen, why, and exactly how to do it.

---

## 1. Google OAuth SSO

**Why:** Albert (u2giants@gmail.com) and the designer team need to log in with Google accounts rather than managing separate Seafile passwords. This also makes the admin account u2giants@gmail.com accessible via SSO.

**Requires:** Albert must create a Google OAuth 2.0 Client ID in Google Cloud Console.

### Steps (Albert does this in Google Cloud Console):
1. Go to https://console.cloud.google.com → APIs & Services → Credentials
2. Click "Create Credentials" → OAuth 2.0 Client ID
3. Application type: **Web application**
4. Name: "Seafile POP Creations" (or anything)
5. Under "Authorized redirect URIs" add exactly:
   ```
   https://seafile.designflow.app/oauth/callback/
   ```
6. Click Create → copy the **Client ID** and **Client Secret**

### Steps (run on server once you have the credentials):
```bash
sudo bash /opt/seafile/CONFIGURE_OAUTH.sh "YOUR_CLIENT_ID" "YOUR_CLIENT_SECRET"
```

That script:
- Backs up the current seahub_settings.py
- Appends the full OAuth config block
- Restarts the seafile container

### Verify:
Open https://seafile.designflow.app — the login page should now show a "Sign in with Google" button.  
Log in as u2giants@gmail.com via Google to confirm admin access works.

---

## 2. NAS Sync Service Account and Libraries

**Why:** The Synology NAS in NYC needs a dedicated Seafile account to push files. This should be a machine account (not a human user) with its own strong password. Libraries are the top-level synced folders in Seafile.

### Create the account and libraries:
```bash
sudo bash /opt/seafile/CREATE_NAS_SYNC_ACCOUNT.sh
```

That script:
- Prompts for the admin password (from `/opt/seafile/CREDENTIALS.txt`)
- Creates `nas-sync@popcreations.com` with a generated password
- Creates three libraries: **Active Projects**, **Assets**, **Seasonal**
- Appends all credentials and library UUIDs to `/opt/seafile/CREDENTIALS.txt`

### After running — give Albert the UUIDs:
The library UUIDs (visible in `/opt/seafile/CREDENTIALS.txt` and in the Seafile URL when opening a library) are needed to configure `seaf-cli` on the Synology NAS. Format: `https://seafile.designflow.app/library/<UUID>/`

### Note on library structure:
Albert may want different library names based on the actual NAS folder structure. Libraries can be renamed or new ones created at any time via the web UI or API.

---

## 3. Designer User Accounts

**Why:** The 8 São Paulo designers need accounts to access the file libraries.

**Two options:**

**Option A — Create accounts manually (admin panel):**  
Admin Panel → Users → Add User → email, temp password, role: Default User.  
Users change their password on first login.

**Option B — Let designers self-register with Google OAuth (after SSO is set up):**  
Once OAuth is configured, designers can click "Sign in with Google" and their accounts are created automatically the first time they log in. Albert then shares the relevant libraries with them.

**Share libraries with designers:**  
Log in as nas-sync@popcreations.com → open a library → Share icon → Share to User → enter designer email → Read/Write.

---

## 4. Synology NAS — seaf-cli Configuration

**Why:** The NYC Synology NAS needs to run `seaf-cli` (Seafile command-line client) in Docker to push the 28TB file library to the Seafile server. This is configured on the NAS side, not on this VPS.

**What Albert needs from this server:**
- Server URL: `https://seafile.designflow.app`
- NAS sync account: `nas-sync@popcreations.com`
- NAS sync password: (from `/opt/seafile/CREDENTIALS.txt` after running step 2)
- Library UUIDs for each folder to sync (from `/opt/seafile/CREDENTIALS.txt`)

**Basic seaf-cli Docker setup on Synology (for reference):**
```bash
docker run -d \
  --name seaf-cli \
  --restart unless-stopped \
  -v /volume1/ActiveProjects:/data/ActiveProjects \
  seafileltd/seaf-cli \
  seaf-cli sync -l <LIBRARY_UUID> \
    -s https://seafile.designflow.app \
    -u nas-sync@popcreations.com \
    -p <NAS_SYNC_PASSWORD> \
    -d /data/ActiveProjects
```

Repeat for each library/folder pair. Initial sync of 28TB will take significant time.

---

## 5. S3 Storage Backend (Optional but Recommended)

**Why:** Currently all file data is stored on the VPS local disk (`/opt/seafile-data/seafile/seafile-data/`). A 28TB library would exceed the 80GB VPS disk. S3-compatible object storage is much cheaper per GB and removes the disk growth concern entirely.

**Albert has an S3-compatible bucket** — credentials were not provided during initial deployment.

**To configure S3 storage:**
1. Edit `/opt/seafile/.env`:
   ```
   SEAF_SERVER_STORAGE_TYPE=s3
   S3_COMMIT_BUCKET=<your-commit-bucket>
   S3_FS_BUCKET=<your-fs-bucket>
   S3_BLOCK_BUCKET=<your-block-bucket>
   S3_KEY_ID=<access-key>
   S3_SECRET_KEY=<secret-key>
   S3_HOST=<endpoint-if-not-aws>    # e.g. us-east-1.linodeobjects.com
   S3_AWS_REGION=us-east-1
   S3_PATH_STYLE_REQUEST=true       # Required for most S3-compatible providers
   ```
2. Restart: `cd /opt/seafile && docker compose -f seafile-server.yml -f caddy.yml up -d`

**Important:** If Seafile already has data on disk when you switch to S3, you must migrate the existing data using `seaf-migrate-db`. Do NOT switch to S3 after file data exists without migrating first.

If configuring S3 before any data is synced, the switch is seamless.

---

## 6. Full-Text Search (Elasticsearch)

**Why:** Seafile Pro includes full-text search inside files (PDFs, Word docs, etc.) via Elasticsearch. It is referenced in `seafevents.conf` but Elasticsearch is not deployed.

**Current state:** The config references `es_host = elasticsearch` which does not exist. Search within file contents will not work, but filename search works fine.

**To add Elasticsearch:**
1. Download the Elasticsearch compose file: `wget https://manual.seafile.com/13.0/repo/docker/pro/elasticsearch.yml`
2. Add `vm.max_map_count=262144` is already set.
3. Add `elasticsearch.yml` to `COMPOSE_FILE` in `.env`
4. Run `docker compose up -d`

**Warning:** Elasticsearch requires significant RAM (~2GB minimum). On a 4GB server this will leave limited headroom. Monitor memory usage carefully.

---

## 7. Notification Server (Optional)

Real-time browser notifications when files change. Currently `ENABLE_NOTIFICATION_SERVER=false`.  
To enable: set `ENABLE_NOTIFICATION_SERVER=true` in `.env` and download `notification-server.yml` from the Seafile manual, add to `COMPOSE_FILE`, and restart.
