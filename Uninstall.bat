@echo off
setlocal
cd /d "%~dp0"

echo.
echo === PSVR2 SteamVR Launcher Uninstaller ===
echo.

set "ORIGINAL_USER=%USERNAME%"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\Uninstall.ps1" -TargetUser "%ORIGINAL_USER%"

echo.
pause
