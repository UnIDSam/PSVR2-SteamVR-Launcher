$ErrorActionPreference = "SilentlyContinue"

$TaskName = "PSVR2 SteamVR Launcher"
$InstallDir = Join-Path $env:LOCALAPPDATA "PSVR2SteamVRLauncher"

Write-Host ""
Write-Host "=== Uninstall PSVR2 SteamVR Launcher ===" -ForegroundColor Cyan
Write-Host ""

schtasks.exe /End /TN "$TaskName" 2>$null | Out-Null
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -eq "PSVR2-SteamVR-Launcher.exe"
    } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}

Write-Host "Uninstalled." -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to close"
