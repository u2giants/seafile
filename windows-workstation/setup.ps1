#Requires -RunAsAdministrator
<#
.SYNOPSIS
    One-shot setup: PopDAM Windows Agent + seaf-cli Seafile upload containers.

.DESCRIPTION
    Run once on a new or replacement machine. Safe to re-run if something
    fails partway through — each step checks whether it is already done.

    What this does:
      1. Downloads and runs the PopDAM Windows Agent installer
      2. Verifies Docker Desktop is installed (you must install it yourself first)
      3. Copies the seaf-cli compose file to C:\ProgramData\seaf-cli\
      4. Prompts for credentials and writes .env
      5. Starts the seaf-cli containers
      6. Registers a scheduled task so containers start automatically on login

    Prerequisites:
      - Windows 10 / 11 with WSL2 enabled
      - Docker Desktop installed with "Start Docker Desktop when you log in" enabled
        Download: https://www.docker.com/products/docker-desktop/
      - This machine on the same LAN as edgesynology1 (the Synology NAS)
      - A NAS account with read access to the "mac" shared folder
      - A Seafile account (same credentials used on the NAS containers)

.NOTES
    Run from an Administrator PowerShell prompt:
      Right-click PowerShell > Run as Administrator
      cd to this folder
      .\setup.ps1
#>

$ErrorActionPreference = "Stop"
$ComposeDir  = "C:\ProgramData\seaf-cli"
$EnvFile     = "$ComposeDir\.env"
$StartScript = "$ComposeDir\wait-and-start.ps1"
$TaskName    = "seaf-cli autostart"

function Write-Step($n, $label) {
    Write-Host "`n[$n/4] $label" -ForegroundColor Yellow
}
function Write-Done($msg) {
    Write-Host "  $msg" -ForegroundColor Green
}
function Write-Info($msg) {
    Write-Host "  $msg"
}

Write-Host "=== PopDAM + seaf-cli Setup ===" -ForegroundColor Cyan

# ── 1. PopDAM Windows Agent ───────────────────────────────────────────────────
Write-Step 1 "PopDAM Windows Agent"
$popdamTask = Get-ScheduledTask -TaskName "PopDAM Windows Render Agent" -ErrorAction SilentlyContinue
if ($popdamTask) {
    Write-Done "Already installed — skipping."
} else {
    Write-Info "Downloading installer from GitHub releases..."
    $installer = "$env:TEMP\popdam-windows-agent-setup.exe"
    Invoke-WebRequest `
        -Uri "https://github.com/u2giants/popdam3/releases/latest/download/popdam-windows-agent-setup.exe" `
        -OutFile $installer `
        -UseBasicParsing
    Write-Info "Launching installer. Complete it, then come back here."
    Start-Process -FilePath $installer -Wait
    $verify = Get-ScheduledTask -TaskName "PopDAM Windows Render Agent" -ErrorAction SilentlyContinue
    if (-not $verify) {
        Write-Host "  WARNING: PopDAM scheduled task not found after install. Continuing anyway." -ForegroundColor DarkYellow
    } else {
        Write-Done "PopDAM Windows Agent installed."
    }
}

# ── 2. Docker Desktop ─────────────────────────────────────────────────────────
Write-Step 2 "Docker Desktop"
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Host @"
  Docker Desktop is not installed or not on PATH.

  Install it from: https://www.docker.com/products/docker-desktop/
  During install, enable "Start Docker Desktop when you log in".
  Then re-run this script.
"@ -ForegroundColor Red
    exit 1
}
Write-Done "Docker found at $($dockerCmd.Source)."

# Verify Docker is currently running (give it up to 60 s to start)
Write-Info "Waiting for Docker daemon..."
$deadline = (Get-Date).AddSeconds(60)
$dockerReady = $false
while ((Get-Date) -lt $deadline) {
    $null = & docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerReady = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $dockerReady) {
    Write-Host "  Docker Desktop doesn't appear to be running. Start it from the system tray and re-run." -ForegroundColor Red
    exit 1
}
Write-Done "Docker daemon is running."

# ── 3. seaf-cli compose files and credentials ─────────────────────────────────
Write-Step 3 "seaf-cli Seafile upload containers"

if (-not (Test-Path $ComposeDir)) {
    New-Item -ItemType Directory -Path $ComposeDir | Out-Null
}

# Copy compose file from script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Copy-Item "$scriptDir\docker-compose.yml" "$ComposeDir\docker-compose.yml" -Force
Write-Done "Copied docker-compose.yml to $ComposeDir"

# Write .env (ask each time if missing; skip if present)
if (Test-Path $EnvFile) {
    Write-Done ".env already exists — using existing credentials."
    Write-Info "Delete $EnvFile and re-run to change credentials."
} else {
    Write-Info "Enter credentials. These are stored in $EnvFile on this machine only."
    Write-Host ""

    $seafUsername = Read-Host "  Seafile username (email)"

    $seafPasswordSec = Read-Host "  Seafile password" -AsSecureString
    $seafPassword    = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                           [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seafPasswordSec))

    $nasUsername = Read-Host "  NAS username  (read access to the 'mac' share on edgesynology1)"

    $nasPasswordSec = Read-Host "  NAS password" -AsSecureString
    $nasPassword    = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                          [Runtime.InteropServices.Marshal]::SecureStringToBSTR($nasPasswordSec))

    @"
SEAF_USERNAME=$seafUsername
SEAF_PASSWORD=$seafPassword
NAS_USERNAME=$nasUsername
NAS_PASSWORD=$nasPassword
"@ | Set-Content $EnvFile -Encoding UTF8
    Write-Done "Credentials written to $EnvFile"
}

# Start containers
Write-Info "Pulling image and starting containers (first run may take a few minutes)..."
Push-Location $ComposeDir
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "  docker compose up failed. Check output above." -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Done "Containers started."

# ── 4. Autostart scheduled task ───────────────────────────────────────────────
Write-Step 4 "Autostart on login"

# Write the helper script that waits for Docker before starting containers
@"
# Auto-generated by setup.ps1 — do not edit manually
`$deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt `$deadline) {
    `$null = & docker info 2>&1
    if (`$LASTEXITCODE -eq 0) {
        Set-Location "$ComposeDir"
        docker compose up -d
        exit 0
    }
    Start-Sleep -Seconds 5
}
"$(Get-Date): Docker not ready after 120 s — seaf-cli containers not started" | Add-Content "$ComposeDir\autostart.log"
exit 1
"@ | Set-Content $StartScript -Encoding UTF8

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
$action   = New-ScheduledTaskAction `
                -Execute "powershell.exe" `
                -Argument "-NonInteractive -WindowStyle Hidden -File `"$StartScript`""
$trigger  = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Force | Out-Null
Write-Done "Scheduled task '$TaskName' registered."

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host @"

=== Setup complete ===

Both the PopDAM Windows Agent and seaf-cli containers are configured.
They start automatically whenever you log in.

Useful commands (run in any terminal):
  docker ps                          — check container status
  docker compose -f "$ComposeDir\docker-compose.yml" logs -f   — live logs

If the CIFS source mounts fail (cannot find edgesynology1 by name),
edit docker-compose.yml and replace "edgesynology1" with the NAS IP address,
then run:  docker compose -f "$ComposeDir\docker-compose.yml" up -d --force-recreate

"@ -ForegroundColor Cyan
