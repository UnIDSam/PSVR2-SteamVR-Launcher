@echo off
setlocal
cd /d "%~dp0"

echo.
echo === PSVR2 SteamVR Launcher Installer ===
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer\Install.ps1"

echo.
if errorlevel 1 (
    echo Installation failed.
) else (
    echo Installation finished.
)

echo.
pause
