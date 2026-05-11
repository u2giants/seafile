# HANDOFF

## What is fully done

### NAS seaf-cli containers (edgesynology1)
Both containers are running and healthy on edgesynology1 with `ghcr.io/u2giants/seafile:seaf-cli-latest`:
- `seaf-cli-char-licensed` — Character Licensed library, 730-day ingest window, 2g memory, cpu_shares 512
- `seaf-cli-generic-decor` — Generic Decor library, 730-day ingest window, 512m memory, cpu_shares 512

The wrapper image (built from `synology-seaf-cli/`) fixes three upstream bugs in `flrnnc/seafile-client` and adds tini as PID 1, a watchdog loop, correct healthcheck exit codes, and stale PID/socket cleanup on `--force-recreate`. See `synology-seaf-cli/README.md` for full details.

### Windows workstation setup scripts
`windows-workstation/` is fully built and ready to deploy:
- `setup.ps1` — one-shot installer run as Administrator; handles PopDAM agent + Docker Desktop check + seaf-cli containers + login autostart
- `docker-compose.yml` — identical service config to the NAS version, but sources mounted via CIFS named volumes (`//edgesynology1/mac/Decor/…`) instead of bind mounts
- `README.md` — machine replacement instructions for Albert

**These scripts have not been run on the Windows machine yet.** They are ready to use.

### Documentation
All docs updated to reflect current state. No stale content.

---

## What is NOT done yet

### 1. Windows workstation cutover (optional — Albert's call)

**What:** Move seaf-cli containers from the NAS to the Windows rendering machine to reduce NAS CPU load.

**Why not done yet:** Requires confirming (a) Docker Desktop is installed on the Windows machine, and (b) what NAS account to use for CIFS credentials. Albert hasn't confirmed Docker Desktop is there.

**Exact next action:**
1. Confirm Docker Desktop is installed on the Windows machine (if not, install it: https://www.docker.com/products/docker-desktop/ — enable "Start Docker Desktop when you log in")
2. Identify a Synology local account with read access to the `mac` shared folder on edgesynology1 for the CIFS mounts — create one if needed via Synology Control Panel → User & Group
3. On the Windows machine: open PowerShell as Administrator, navigate to `windows-workstation/`, run `.\setup.ps1`
4. Enter credentials when prompted: Seafile = `nas-sync@popcre.com` + password from `/opt/seafile/CREDENTIALS.txt` on VPS; NAS = the account from step 2
5. Verify `docker ps` shows both containers healthy and logs show "synchronized"
6. Tell Claude to stop the NAS seaf-cli containers

**Risk:** On first start, seaf-daemon SHA1-hashes every file to build its sync tree. For the Character Licensed library (~467k files), expect 200-300% CPU for several hours. This is normal.

**Risk:** If `edgesynology1` doesn't resolve from inside Docker Desktop's WSL2 VM, the CIFS mounts will fail. Fix: edit `C:\ProgramData\seaf-cli\docker-compose.yml` and replace `edgesynology1` with the NAS IP address.

### 2. Designer user accounts (pre-existing, unrelated to seaf-cli work)

8 São Paulo designers still need Seafile library access. The system is ready; they just haven't been invited.

**Exact next action:** Send designers `https://seafile.designflow.app`. They click "Sign in with Microsoft" and log in with their POP Creations M365 account — accounts create automatically. Albert then shares Character Licensed and Generic Decor libraries with each: open library → Share icon → Share to User → designer email → Read/Write.

---

## Decisions made and why

- **seaf-cli on Windows uses CIFS named volumes, not bind mounts** — Docker Desktop on Windows can't bind-mount UNC paths (`\\server\share`). CIFS named volumes mount via the Linux CIFS stack inside WSL2 and work reliably over LAN.
- **One PowerShell script bundles PopDAM + seaf-cli** — Albert's explicit goal was "one thing to install" for machine recovery. `setup.ps1` is idempotent (each step checks if already done), so re-running on an existing machine is safe.
- **seaf-cli on Windows or NAS — not both** — two seaf-cli processes syncing the same library concurrently is unsupported and would cause conflicts. The cutover requires stopping the old deployment.
- **CPU spike on first start is unavoidable** — seaf-daemon must SHA1-hash every file byte. SEAF_UPLOAD_LIMIT/SEAF_DOWNLOAD_LIMIT only throttle network, not hashing. This is inherent to seaf-cli's design.

---

## Context that exists only in this conversation

- The Windows rendering machine already runs the PopDAM Windows Agent as a Windows Scheduled Task ("PopDAM Windows Render Agent"). `setup.ps1` detects this and skips the PopDAM install step.
- The Synology NAS has two NICs. Albert asked about dedicating one to seaf-cli traffic. Decision: not worth doing. seaf-cli only reads from the NAS during the hourly staging pass; the rest of the time it's uploading to the internet. No NIC contention in practice.
- NAS seaf-cli on the NAS uses `cpu_shares: 512` (not `cpus:`) because Synology's kernel does not support CFS CPU quota cgroups. Hard `cpus` limits were tried and returned "NanoCPUs can not be set". On Windows, this is not an issue — Docker Desktop on WSL2 supports both.
