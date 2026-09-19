param(
    [switch]$StartNow = $true,
    [string]$TargetUser = $env:USERNAME,
    [switch]$Elevated
)

$ErrorActionPreference = "Stop"

$Version = "0.2.5"
$TaskName = "PSVR2 SteamVR Launcher"
$InstallDir = Join-Path $env:LOCALAPPDATA "PSVR2SteamVRLauncher"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $SourceDir
$ExeSource = Join-Path $PackageRoot "PSVR2-SteamVR-Launcher.exe"
$ExeDest = Join-Path $InstallDir "PSVR2-SteamVR-Launcher.exe"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

# ------------------------------------------------------------
# Elevate automatically if needed.
# We preserve the original interactive Windows user so the
# scheduled task still belongs to / runs for that user.
# ------------------------------------------------------------

if (-not (Test-IsAdministrator)) {

    Write-Host "Administrator permission is required to update the Windows startup task."
    Write-Host "Opening the Windows UAC prompt..."

    $args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-TargetUser", "`"$TargetUser`"",
        "-Elevated"
    )

    if ($StartNow) {
        $args += "-StartNow"
    }

    try {
        $proc = Start-Process `
            -FilePath "powershell.exe" `
            -ArgumentList $args `
            -Verb RunAs `
            -Wait `
            -PassThru

        exit $proc.ExitCode
    }
    catch {
        Write-Host ""
        Write-Host "ERROR: Administrator permission was not granted." -ForegroundColor Red
        Write-Host $_.Exception.Message
        exit 1
    }
}

Write-Host ""
Write-Host "=== PSVR2 SteamVR Launcher v$Version Setup ===" -ForegroundColor Cyan
Write-Host "Installing for Windows user: $TargetUser"
Write-Host ""

if (-not (Test-Path $ExeSource)) {
    Write-Host "ERROR: PSVR2-SteamVR-Launcher.exe was not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "Run Install.bat from the extracted GitHub RELEASE ZIP."
    Write-Host "Do not run this installer directly from the source-code package."
    exit 1
}

# Resolve the target user's LocalAppData.
# For normal same-user UAC elevation, use the known user profile path.
$TargetProfile = Join-Path $env:SystemDrive "Users\$TargetUser"
$TargetLocalAppData = Join-Path $TargetProfile "AppData\Local"
$InstallDir = Join-Path $TargetLocalAppData "PSVR2SteamVRLauncher"
$ExeDest = Join-Path $InstallDir "PSVR2-SteamVR-Launcher.exe"

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

# ------------------------------------------------------------
# Stop and remove existing startup task
# ------------------------------------------------------------

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($task) {
    Write-Host "Existing startup task found - stopping it..."

    Stop-ScheduledTask `
        -TaskName $TaskName `
        -ErrorAction SilentlyContinue

    Write-Host "Removing old startup task..."

    Unregister-ScheduledTask `
        -TaskName $TaskName `
        -Confirm:$false `
        -ErrorAction SilentlyContinue
}

# ------------------------------------------------------------
# Stop all running launcher processes
# ------------------------------------------------------------

$running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -eq "PSVR2-SteamVR-Launcher.exe"
    }

if ($running) {
    Write-Host "Existing launcher detected - stopping old version..."

    foreach ($proc in $running) {
        try {
            Stop-Process `
                -Id $proc.ProcessId `
                -Force `
                -ErrorAction Stop
        }
        catch {
            Write-Host "Could not stop PID $($proc.ProcessId) immediately."
        }
    }
}

# ------------------------------------------------------------
# Wait for old launcher to fully exit and release the EXE
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
    Write-Host "ERROR: The old launcher is still running." -ForegroundColor Red
    Write-Host "Close it from Task Manager and run Install.bat again."
    exit 1
}

Start-Sleep -Milliseconds 500

# ------------------------------------------------------------
# Copy with retries for transient Windows file locks
# ------------------------------------------------------------

$copySucceeded = $false

for ($attempt = 1; $attempt -le 10; $attempt++) {

    try {
        Copy-Item `
            $ExeSource `
            $ExeDest `
            -Force `
            -ErrorAction Stop

        $copySucceeded = $true
        break
    }
    catch {
        if ($attempt -eq 10) {
            Write-Host ""
            Write-Host "ERROR: Could not replace the installed EXE." -ForegroundColor Red
            Write-Host $_.Exception.Message
            exit 1
        }

        Write-Host "Installed EXE is still busy - retrying ($attempt/10)..."
        Start-Sleep -Milliseconds 500
    }
}

# Remove Mark-of-the-Web from the installed copy.
Unblock-File -Path $ExeDest -ErrorAction SilentlyContinue

# ------------------------------------------------------------
# Create clean per-user logon task.
# Registration is elevated, but the launcher itself runs with
# normal user privileges.
# ------------------------------------------------------------

$Action = New-ScheduledTaskAction -Execute $ExeDest
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $TargetUser

$Principal = New-ScheduledTaskPrincipal `
    -UserId $TargetUser `
    -LogonType Interactive `
    -RunLevel Limited

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

Write-Host "Creating Windows startup task..."

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Automatically starts and stops SteamVR with the PSVR2 headset." `
    -Force `
    -ErrorAction Stop | Out-Null

if ($StartNow) {
    Write-Host "Starting PSVR2 SteamVR Launcher v$Version..."

    Start-ScheduledTask `
        -TaskName $TaskName `
        -ErrorAction Stop
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

exit 0
