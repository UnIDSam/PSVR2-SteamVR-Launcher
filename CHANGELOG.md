# Changelog

## 0.2.5

- Fixed `Register-ScheduledTask: Access denied` during upgrades/install
- Installer now automatically requests UAC administrator permission
- Preserves the original Windows user when installing elevated
- Removes the old scheduled task before recreating it
- Launcher task still runs with normal user privileges
- Uninstaller now handles task removal with UAC as well
- Keeps all v0.2.4 support, logging, license and tray features

## 0.2.4

- Added automatic log rotation at ~1 MB
- Keeps up to 3 backup log files
- Added Clear Logs tray command
- Added Project / Support tray link
- Added Report a Bug tray link
- Added Check Latest Release tray link
- About dialog now shows author, version, support URL and disclaimer
- Added GitHub support link to installer
- Added MIT license
- Added non-affiliation disclaimer
- Keeps all v0.2.3 installer fixes, v0.2.2 shutdown fixes and v0.2.1 single-instance fixes

## 0.2.3

- Fixed installer race when upgrading over a running launcher
- Installer now waits until all old launcher processes have exited
- Added retry loop for transient Windows EXE file locks
- Installer now clearly reports upgrade progress
- Fixed stale installer version banner
- Install.bat now stays open so errors can be read
- Keeps all v0.2.2 SteamVR shutdown and v0.2.1 single-instance fixes

## 0.2.2

- Improved SteamVR shutdown reliability
- Kill `vrserver.exe` first to prevent SteamVR processes being kept alive/restarted
- Retry targeted SteamVR shutdown for up to 5 seconds
- Still never terminates `steam.exe` or `steamwebhelper.exe`
- Keeps all v0.2.1 tray, settings, icon, logging and single-instance fixes

## 0.2.1

- Fixed single-instance protection on 64-bit Windows
- All versions now share one named mutex so old/new launcher copies cannot coexist
- Restored proven-stable PSVR2 timing values
- Added Steam PID diagnostics at the exact PSVR2 power-on transition
- Keeps all v0.2 tray, settings, icon and logging features

## 0.2.0

- Added custom application icon
- Added Windows system tray icon
- Added tray status display
- Added manual Start SteamVR command
- Added manual Stop SteamVR command
- Added Settings window
- Added configurable detection/startup timings
- Added configurable Steam auto-start
- Added optional notifications
- Added optional detailed logging
- Added Open Log and Open Install Folder commands
- Added About/version dialog
- Improved shutdown speed
- Kept targeted SteamVR-only shutdown so Steam remains running
- Permanent settings and log paths under LocalAppData

## 0.1.1

- Faster PSVR2 detection and SteamVR startup
- Faster SteamVR shutdown response
- Permanent log path under LocalAppData
- Clearer installer diagnostics

## 0.1.0

- Initial public release
- Automatic PSVR2 headset detection
- Automatic SteamVR start/stop
- Scheduled-task installer/uninstaller
