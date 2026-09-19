param(
    [switch]$StartNow = $true
)

$ErrorActionPreference = "Stop"

$Version = "0.2.4"
$TaskName = "PSVR2 SteamVR Launcher"
$InstallDir = Join-Path $env:LOCALAPPDATA "PSVR2SteamVRLauncher"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExeSource = Join-Path (Split-Path -Parent $SourceDir) "PSVR2-SteamVR-Launcher.exe"
$ExeDest = Join-Path $InstallDir "PSVR2-SteamVR-Launcher.exe"

Write-Host ""
Write-Host "=== PSVR2 SteamVR Launcher v$Version Setup ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $ExeSource)) {
    Write-Host "ERROR: PSVR2-SteamVR-Launcher.exe was not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "Run Install.bat from the extracted GitHub RELEASE ZIP."
    Write-Host "Do not run this installer directly from the source-code package."
    Write-Host ""
    Read-Host "Press Enter to close"
    exit 1
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# ------------------------------------------------------------
# Stop scheduled task first
# ------------------------------------------------------------

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($task) {
    Write-Host "Existing startup task found - stopping it..."
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
}

# ------------------------------------------------------------
# Stop every running launcher process
# ------------------------------------------------------------

$running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -eq "PSVR2-SteamVR-Launcher.exe"
    }

if ($running) {
    Write-Host "Existing launcher detected - stopping old version..."

    foreach ($proc in $running) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
        }
        catch {
            Write-Host "Could not stop PID $($proc.ProcessId) immediately."
        }
    }
}

# ------------------------------------------------------------
# Wait until every launcher process is REALLY gone.
# PyInstaller one-file builds can take a moment to release the EXE.
# ------------------------------------------------------------

$deadline = (Get-Date).AddSeconds(15)

do {
    $stillRunning = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -eq "PSVR2-SteamVR-Launcher.exe"
        }

    if (-not $stillRunning) {
        break
    }

    Start-Sleep -Milliseconds 250

} while ((Get-Date) -lt $deadline)

if ($stillRunning) {
    Write-Host ""
    Write-Host "ERROR: The old launcher is still running and could not be stopped." -ForegroundColor Red
    Write-Host "Please close it from Task Manager and run Install.bat again."
    Write-Host ""
    Read-Host "Press Enter to close"
    exit 1
}

# Extra grace period for Windows to release file handles.
Start-Sleep -Milliseconds 500

# ------------------------------------------------------------
# Copy with retries in case Windows still has a transient lock
# ------------------------------------------------------------

$copySucceeded = $false

for ($attempt = 1; $attempt -le 10; $attempt++) {

    try {
        Copy-Item $ExeSource $ExeDest -Force -ErrorAction Stop
        $copySucceeded = $true
        break
    }
    catch {
        if ($attempt -eq 10) {
            Write-Host ""
            Write-Host "ERROR: Could not replace the installed EXE after 10 attempts." -ForegroundColor Red
            Write-Host $_.Exception.Message
            Write-Host ""
            Read-Host "Press Enter to close"
            exit 1
        }

        Write-Host "Installed EXE is still busy - retrying ($attempt/10)..."
        Start-Sleep -Milliseconds 500
    }
}

# Remove Mark-of-the-Web from installed copy.
Unblock-File -Path $ExeDest -ErrorAction SilentlyContinue

# ------------------------------------------------------------
# Recreate startup task
# ------------------------------------------------------------

$Action = New-ScheduledTaskAction -Execute $ExeDest
$Trigger = New-ScheduledTaskTrigger -AtLogOn

$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Automatically starts and stops SteamVR with the PSVR2 headset." `
    -Force | Out-Null

if ($StartNow) {
    Write-Host "Starting PSVR2 SteamVR Launcher v$Version..."
    Start-ScheduledTask -TaskName $TaskName
}

Write-Host ""
Write-Host "Installed successfully." -ForegroundColor Green
Write-Host "Version: v$Version"
Write-Host "Install folder: $InstallDir"
Write-Host "Log file: $InstallDir\psvr2_steamvr.log"
Write-Host "Settings file: $InstallDir\settings.json"
Write-Host "Windows startup task: $TaskName"
Write-Host ""
Write-Host "Look for the PSVR2 SteamVR Launcher icon in the Windows system tray."
Write-Host "Support: https://github.com/UnIDSam/PSVR2-SteamVR-Launcher"
Write-Host ""
Read-Host "Press Enter to close"
