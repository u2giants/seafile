# Windows Workstation Setup

This folder sets up two things on the Windows rendering machine:

1. **PopDAM Windows Agent** — renders AI/TIFF files for the popdam application
2. **seaf-cli containers** — upload NAS design files to Seafile (offloaded from the NAS)

Both start automatically when you log in.

---

## Prerequisites (do these once, before running setup)

1. **WSL2 enabled** — open PowerShell as Administrator and run:
   ```
   wsl --install
   ```
   Restart if prompted.

2. **Docker Desktop installed** — download from https://www.docker.com/products/docker-desktop/
   - During setup: enable **"Start Docker Desktop when you log in"**
   - After install: open Docker Desktop once, accept the license, confirm it starts

---

## First-time install

1. Open **PowerShell as Administrator** (right-click the Start menu → Windows PowerShell (Admin))
2. Navigate to this folder:
   ```powershell
   cd "path\to\this\folder"
   ```
3. Run:
   ```powershell
   .\setup.ps1
   ```
4. Follow the prompts:
   - The PopDAM installer will open — complete it, then return to PowerShell
   - Enter the Seafile sync account credentials (`nas-sync@popcre.com` + password from `/opt/seafile/CREDENTIALS.txt` on the VPS)
   - Enter a NAS account username and password (needs read access to the `mac` shared folder on edgesynology1)

That's it. Both the PopDAM agent and the Seafile containers will start automatically from now on.

---

## Replacing the machine

1. On the new machine, install WSL2 and Docker Desktop (see Prerequisites above)
2. Copy this entire folder to the new machine
3. Run `setup.ps1` as Administrator
4. Enter credentials when prompted

You do not need to copy anything else. The sync state rebuilds automatically from the NAS.

---

## Cutting over from the NAS (first-time only)

The Seafile upload containers currently run on the Synology NAS. Once this Windows machine is set up and verified healthy, ask Claude to stop the NAS containers — it has NAS access and knows the exact commands. Tell it: "stop the seaf-cli containers on the NAS."

Do not run both simultaneously — two clients syncing the same library at once will conflict.

---

## Troubleshooting

**Containers don't start on login:**
Open Task Scheduler, find "seaf-cli autostart", and run it manually to see the error. Or check `C:\ProgramData\seaf-cli\autostart.log`.

**CIFS mount fails (can't connect to NAS):**
The NAS hostname `edgesynology1` may not resolve from inside Docker. Edit `C:\ProgramData\seaf-cli\docker-compose.yml`, replace `edgesynology1` with the NAS IP address (check it in Synology Control Panel → Info Center), then run:
```powershell
cd C:\ProgramData\seaf-cli
docker compose up -d --force-recreate
```

**To change credentials:**
Delete `C:\ProgramData\seaf-cli\.env` and re-run `setup.ps1`.

**To check sync status:**
```powershell
docker exec seaf-cli-char-licensed python3 /home/seafile/entrypoint.py --healthcheck
docker exec seaf-cli-generic-decor  python3 /home/seafile/entrypoint.py --healthcheck
```
