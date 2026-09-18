# PSVR2 SteamVR Launcher

A small Windows utility that automatically starts SteamVR when a PSVR2 headset is powered on and closes SteamVR when the headset is powered off.

## What it does

- Watches the PSVR2 headset USB interface (`VID_054C`, `PID_0CDE`, `MI_00`)
- Ignores the PSVR2 controllers
- Starts SteamVR when the headset is turned on
- Closes only SteamVR-owned processes when the headset is turned off
- Does **not** terminate `steam.exe`
- Prevents multiple copies from running
- Writes a local diagnostic log
- Runs automatically at Windows logon

## One-click install

Download the latest release ZIP, extract it, and double-click:

`Install.bat`

The installer copies the standalone EXE to:

`%LOCALAPPDATA%\PSVR2SteamVRLauncher`

and creates a Windows Scheduled Task named:

`PSVR2 SteamVR Launcher`

No Python installation is required for release builds.

## Uninstall

Double-click:

`Uninstall.bat`

## Current timing

- PSVR2 ON debounce: 1 second
- PSVR2 OFF debounce: 2 seconds
- Steam stable check: 1 second

## Important implementation note

Earlier versions used SteamVR's global quit URI. On the test system, that was associated with Steam itself exiting. This project instead shuts down only SteamVR-owned processes:

- `vrdashboard.exe`
- `vrwebhelper.exe`
- `vrmonitor.exe`
- `vrcompositor.exe`
- `vrserver.exe`

It intentionally leaves these alone:

- `steam.exe`
- `steamwebhelper.exe`

## Development

Run from source:

```powershell
python src\psvr2_steamvr.py
```

Build a standalone EXE locally:

```powershell
python -m pip install pyinstaller
pyinstaller --onefile --noconsole --name PSVR2-SteamVR-Launcher src\psvr2_steamvr.py
```

## Releases

Pushing a Git tag such as `v0.1.0` triggers the included GitHub Actions workflow. It:

1. builds the Windows EXE with PyInstaller;
2. creates a release ZIP containing the EXE and installer;
3. publishes the ZIP and EXE to a GitHub Release.

## Requirements

- Windows 10/11
- Steam
- SteamVR
- PSVR2 PC connection / adapter configured and working
