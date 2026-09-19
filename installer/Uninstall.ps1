param(
    [string]$TargetUser = $env:USERNAME
)

$ErrorActionPreference = "Stop"

$TaskName = "PSVR2 SteamVR Launcher"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

if (-not (Test-IsAdministrator)) {

    Write-Host "Administrator permission is required to remove the startup task."
    Write-Host "Opening the Windows UAC prompt..."

    $args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-TargetUser", "`"$TargetUser`""
    )

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
        Write-Host "ERROR: Administrator permission was not granted." -ForegroundColor Red
        exit 1
    }
}

$TargetProfile = Join-Path $env:SystemDrive "Users\$TargetUser"
$InstallDir = Join-Path $TargetProfile "AppData\Local\PSVR2SteamVRLauncher"

Write-Host ""
Write-Host "=== Uninstall PSVR2 SteamVR Launcher ===" -ForegroundColor Cyan
Write-Host ""

Stop-ScheduledTask `
    -TaskName $TaskName `
    -ErrorAction SilentlyContinue

Unregister-ScheduledTask `
    -TaskName $TaskName `
    -Confirm:$false `
    -ErrorAction SilentlyContinue

Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -eq "PSVR2-SteamVR-Launcher.exe"
    } |
    ForEach-Object {
        Stop-Process `
            -Id $_.ProcessId `
            -Force `
            -ErrorAction SilentlyContinue
    }

Start-Sleep -Milliseconds 500

if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}

Write-Host "Uninstalled successfully." -ForegroundColor Green
exit 0
