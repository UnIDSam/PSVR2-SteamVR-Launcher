param(
    [switch]$StartNow = $true
)

$ErrorActionPreference = "Stop"

$AppName = "PSVR2 SteamVR Launcher"
$TaskName = "PSVR2 SteamVR Launcher"
$InstallDir = Join-Path $env:LOCALAPPDATA "PSVR2SteamVRLauncher"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExeSource = Join-Path (Split-Path -Parent $SourceDir) "PSVR2-SteamVR-Launcher.exe"
$ExeDest = Join-Path $InstallDir "PSVR2-SteamVR-Launcher.exe"

Write-Host ""
Write-Host "=== PSVR2 SteamVR Launcher Setup ===" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $ExeSource)) {
    throw "PSVR2-SteamVR-Launcher.exe was not found next to the installer."
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# Stop old scheduled task / process if present.
schtasks.exe /End /TN "$TaskName" 2>$null | Out-Null

Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "PSVR2-SteamVR-Launcher.exe" -and
        $_.ExecutablePath -eq $ExeDest
    } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Copy-Item $ExeSource $ExeDest -Force

# Create per-user task at logon. Quoting through PowerShell scheduled-task cmdlets
# avoids the path-with-spaces problems that schtasks /create can have.
$Action = New-ScheduledTaskAction -Execute $ExeDest
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Automatically starts and stops SteamVR with the PSVR2 headset." `
    -Force | Out-Null

if ($StartNow) {
    Start-ScheduledTask -TaskName $TaskName
}

Write-Host ""
Write-Host "Installed successfully." -ForegroundColor Green
Write-Host "Install folder: $InstallDir"
Write-Host "Windows startup task: $TaskName"
Write-Host ""
Write-Host "Turn the PSVR2 headset on to start SteamVR."
Write-Host "Turn it off to close SteamVR."
Write-Host ""
Write-Host "A log file will be written beside the installed EXE."
Write-Host ""
Read-Host "Press Enter to close"
