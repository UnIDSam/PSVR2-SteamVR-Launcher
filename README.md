# PSVR2 SteamVR Launcher

A small Windows tray utility that automatically starts SteamVR when a PSVR2 headset is powered on and closes SteamVR when the headset is powered off.

## v0.2.4

This is the complete desktop/tray release.

### Features

- Detects the PSVR2 headset through its dedicated USB interface
- Ignores PSVR2 controller activity
- Automatically starts SteamVR when the headset powers on
- Automatically closes only SteamVR-owned processes when the headset powers off
- Never force-closes `steam.exe`
- Runs automatically at Windows logon
- Custom application and system tray icon
- System tray menu
- Manual **Start SteamVR now**
- Manual **Stop SteamVR now**
- Settings window
- Configurable PSVR2 ON/OFF delay
- Configurable Steam ready delay
- Configurable polling interval
- Optional Steam auto-start
- Optional tray notifications
- Optional detailed logging
- Open log file from tray
- Open install folder from tray
- About/version information
- Single-instance protection

## Default timing

- PSVR2 ON delay: 1.0 second
- PSVR2 OFF delay: 2.0 seconds
- Steam ready delay: 1.0 second
- Polling interval: 0.75 seconds

These values can be changed from the tray icon:

`Right-click tray icon -> Settings`

## Install

Download the release ZIP, extract it, then double-click:

`Install.bat`

No Python installation is required.

The app installs to:

`%LOCALAPPDATA%\PSVR2SteamVRLauncher`


## Windows SmartScreen

GitHub release builds are currently unsigned, so Windows may show an **Unknown publisher** SmartScreen warning when you run the EXE directly from Downloads.

The installer removes the downloaded-file Mark-of-the-Web from the installed copy before the Scheduled Task starts it.

For a completely warning-free public distribution, the EXE would need to be signed with a trusted Windows code-signing certificate.

## Log

`%LOCALAPPDATA%\PSVR2SteamVRLauncher\psvr2_steamvr.log`

## Settings

`%LOCALAPPDATA%\PSVR2SteamVRLauncher\settings.json`

## Tray menu

- Status
- Start SteamVR now
- Stop SteamVR now
- Settings
- Open log file
- Open install folder
- About
- Exit

## Safe SteamVR shutdown

The launcher deliberately avoids SteamVR's global quit URI because it caused the Steam client itself to exit on the original test system.

It shuts down only SteamVR-owned processes:

- `vrdashboard.exe`
- `vrwebhelper.exe`
- `vrmonitor.exe`
- `vrcompositor.exe`
- `vrserver.exe`

It does not terminate:

- `steam.exe`
- `steamwebhelper.exe`

## Uninstall

Double-click:

`Uninstall.bat`

## Development build

```powershell
python -m pip install pyinstaller pillow pystray

pyinstaller `
  --onefile `
  --noconsole `
  --icon assets\icon.ico `
  --add-data "assets\icon.png;assets" `
  --add-data "assets\icon.ico;assets" `
  --name PSVR2-SteamVR-Launcher `
  src\psvr2_steamvr.py
```

## Requirements

- Windows 10/11
- Steam
- SteamVR
- PSVR2 PC connection / adapter configured and working


## Support

For support, updates, bug reports, and releases:

https://github.com/UnIDSam/PSVR2-SteamVR-Launcher

Use GitHub Issues for bugs and support requests.

## Log rotation

The launcher keeps logs small automatically.

- Current log: `psvr2_steamvr.log`
- Rotates at approximately 1 MB
- Keeps up to 3 backup logs
- Oldest logs are deleted automatically

You can also use:

`Right-click tray icon -> Clear logs`

## Disclaimer

This project is not affiliated with, endorsed by, or sponsored by Sony, PlayStation, Valve, Steam, or SteamVR.

## License

MIT License. See `LICENSE`.
