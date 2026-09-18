param(
    [switch]$StartNow = $true
)

$ErrorActionPreference = "Stop"

$TaskName = "PSVR2 SteamVR Launcher"
$InstallDir = Join-Path $env:LOCALAPPDATA "PSVR2SteamVRLauncher"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExeSource = Join-Path (Split-Path -Parent $SourceDir) "PSVR2-SteamVR-Launcher.exe"
$ExeDest = Join-Path $InstallDir "PSVR2-SteamVR-Launcher.exe"

Write-Host ""
Write-Host "=== PSVR2 SteamVR Launcher v0.2.0 Setup ===" -ForegroundColor Cyan
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

schtasks.exe /End /TN "$TaskName" 2>$null | Out-Null

Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "PSVR2-SteamVR-Launcher.exe"
    } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Copy-Item $ExeSource $ExeDest -Force

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
    Start-ScheduledTask -TaskName $TaskName
}

Write-Host ""
Write-Host "Installed successfully." -ForegroundColor Green
Write-Host "Install folder: $InstallDir"
Write-Host "Log file: $InstallDir\psvr2_steamvr.log"
Write-Host "Settings file: $InstallDir\settings.json"
Write-Host "Windows startup task: $TaskName"
Write-Host ""
Write-Host "Look for the PSVR2 SteamVR Launcher icon in the Windows system tray."
Write-Host ""
Read-Host "Press Enter to close"
