import ctypes
import csv
import io
import os
import re
import subprocess
import sys
import time
from datetime import datetime


# ============================================================
# SETTINGS
# ============================================================

PSVR2_DEVICE = r"USB\VID_054C&PID_0CDE&MI_00"

CHECK_INTERVAL = 0.75

# Short debounce: PSVR2 must stay ON this long before accepting ON.
ON_STABLE_SECONDS = 1.0

# Short debounce: PSVR2 must stay OFF this long before accepting OFF.
OFF_STABLE_SECONDS = 2.0

# Steam only needs a very short stable window before SteamVR is allowed to start.
STEAM_STABLE_SECONDS = 1.0

# Maximum time we will wait for Steam to finish starting/updating.
STEAM_READY_TIMEOUT = 90.0


# ============================================================
# WINDOWS FLAGS
# ============================================================

CREATE_NO_WINDOW = 0x08000000

APP_VERSION = "0.1.0"


# ============================================================
# LOGGING
# ============================================================

SCRIPT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

LOG_FILE = os.path.join(
    SCRIPT_DIR,
    "psvr2_steamvr.log"
)


def log(message):

    try:

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        with open(
            LOG_FILE,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                f"[{timestamp}] {message}\n"
            )

    except Exception:
        pass


# ============================================================
# SINGLE INSTANCE
# ============================================================

kernel32 = ctypes.windll.kernel32

mutex_handle = kernel32.CreateMutexW(
    None,
    False,
    "PSVR2_SteamVR_Launcher_SingleInstance"
)

ERROR_ALREADY_EXISTS = 183

if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:

    log(
        "Another launcher instance is already running. "
        "Exiting."
    )

    sys.exit(0)


# ============================================================
# PROCESS HELPERS
# ============================================================

def get_process_pids(process_name):

    try:

        result = subprocess.run(
            [
                "tasklist",
                "/FI",
                f"IMAGENAME eq {process_name}",
                "/FO",
                "CSV",
                "/NH"
            ],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW
        )

        pids = []

        reader = csv.reader(
            io.StringIO(result.stdout)
        )

        for row in reader:

            if len(row) < 2:
                continue

            if (
                row[0].lower()
                != process_name.lower()
            ):
                continue

            try:
                pids.append(
                    int(row[1])
                )

            except ValueError:
                pass

        return pids

    except Exception as e:

        log(
            f"Process check failed for "
            f"{process_name}: {e}"
        )

        return []


def process_running(process_name):

    return bool(
        get_process_pids(process_name)
    )


# ============================================================
# STEAM STATUS FOR LOG FILE
# ============================================================

last_steam_status = None


def get_steam_status():

    steam_pids = get_process_pids(
        "steam.exe"
    )

    webhelper_pids = get_process_pids(
        "steamwebhelper.exe"
    )

    if not steam_pids:
        return "NOT RUNNING"

    if not webhelper_pids:
        return (
            "STARTING / UPDATING "
            f"| steam.exe PID(s): {steam_pids} "
            "| steamwebhelper.exe: NOT RUNNING"
        )

    return (
        "RUNNING "
        f"| steam.exe PID(s): {steam_pids} "
        f"| steamwebhelper count: {len(webhelper_pids)}"
    )


def log_steam_status(force=False):

    global last_steam_status

    status = get_steam_status()

    if force or status != last_steam_status:
        log(f"STEAM STATUS -> {status}")
        last_steam_status = status


# ============================================================
# FIND STEAM INSTALLATION
# ============================================================

def find_steam_exe():

    possible_paths = [
        os.path.expandvars(
            r"%ProgramFiles(x86)%\Steam\steam.exe"
        ),

        os.path.expandvars(
            r"%ProgramFiles%\Steam\steam.exe"
        ),

        r"C:\Steam\steam.exe",
        r"D:\Steam\steam.exe",
        r"E:\Steam\steam.exe",
        r"F:\Steam\steam.exe",
    ]

    for path in possible_paths:

        if os.path.exists(path):
            return path

    return None


# ============================================================
# FIND STEAM LIBRARIES
# ============================================================

def get_steam_libraries():

    possible_roots = [
        os.path.expandvars(
            r"%ProgramFiles(x86)%\Steam"
        ),

        os.path.expandvars(
            r"%ProgramFiles%\Steam"
        ),

        r"C:\Steam",
        r"D:\Steam",
        r"E:\Steam",
        r"F:\Steam",
    ]

    libraries = set()

    for root in possible_roots:

        if os.path.exists(root):
            libraries.add(root)

    for root in possible_roots:

        vdf = os.path.join(
            root,
            "steamapps",
            "libraryfolders.vdf"
        )

        if not os.path.exists(vdf):
            continue

        try:

            with open(
                vdf,
                "r",
                encoding="utf-8"
            ) as f:

                content = f.read()

            matches = re.findall(
                r'"path"\s+"([^"]+)"',
                content
            )

            for path in matches:

                path = path.replace(
                    "\\\\",
                    "\\"
                )

                libraries.add(path)

        except Exception as e:

            log(
                f"Could not read "
                f"libraryfolders.vdf: {e}"
            )

    return libraries


# ============================================================
# FIND VRMONITOR
# ============================================================

def find_vrmonitor():

    for library in get_steam_libraries():

        vrmonitor = os.path.join(
            library,
            "steamapps",
            "common",
            "SteamVR",
            "bin",
            "win64",
            "vrmonitor.exe"
        )

        if os.path.exists(vrmonitor):

            return vrmonitor

    return None


# ============================================================
# PSVR2 STATE
# ============================================================

def headset_is_on():

    command = (
        "Get-PnpDevice | "
        "Where-Object { "
        "$_.InstanceId -like '"
        + PSVR2_DEVICE +
        r"\*' -and "
        "$_.Status -eq 'OK' "
        "} | "
        "Select-Object -First 1"
    )

    try:

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command
            ],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=10
        )

        if result.returncode != 0:

            log(
                "PSVR2 PowerShell check failed. "
                "Ignoring reading."
            )

            return None

        return bool(
            result.stdout.strip()
        )

    except Exception as e:

        log(
            f"PSVR2 detection error: {e}"
        )

        return None


# ============================================================
# STEAMVR STATE
# ============================================================

def steamvr_running():

    return process_running(
        "vrmonitor.exe"
    )


# ============================================================
# START STEAM IF REQUIRED
# ============================================================

def ensure_steam_started():

    if process_running("steam.exe"):

        log(
            "Steam is already running."
        )

        return True

    steam_exe = find_steam_exe()

    if steam_exe is None:

        log(
            "ERROR: steam.exe could not be found."
        )

        return False

    log(
        "Steam is not running."
    )

    log(
        "Starting Steam and waiting for it "
        "to become ready."
    )

    try:

        subprocess.Popen(
            [
                steam_exe,
                "-silent"
            ],
            cwd=os.path.dirname(
                steam_exe
            ),
            creationflags=CREATE_NO_WINDOW
        )

        return True

    except Exception as e:

        log(
            f"Could not start Steam: {e}"
        )

        return False


# ============================================================
# WAIT UNTIL STEAM IS ACTUALLY READY
# ============================================================

def wait_for_steam_ready():

    log(
        "Waiting for Steam to be fully ready..."
    )

    log_steam_status(force=True)

    started_waiting = time.monotonic()

    stable_since = None

    previous_steam_pids = None

    while True:

        now = time.monotonic()

        log_steam_status()

        # ----------------------------------------------------
        # If headset was actually turned OFF while we're
        # waiting, cancel the launch.
        # ----------------------------------------------------

        headset_state = headset_is_on()

        if headset_state is False:

            log(
                "PSVR2 turned OFF while waiting "
                "for Steam. Launch cancelled."
            )

            return False


        # ----------------------------------------------------
        # Timeout protection
        # ----------------------------------------------------

        if (
            now - started_waiting
            >= STEAM_READY_TIMEOUT
        ):

            log(
                "Steam did not become ready within "
                "90 seconds."
            )

            return False


        # ----------------------------------------------------
        # Steam process
        # ----------------------------------------------------

        steam_pids = get_process_pids(
            "steam.exe"
        )

        webhelper_pids = get_process_pids(
            "steamwebhelper.exe"
        )


        # ----------------------------------------------------
        # Steam updater/restart situation:
        #
        # During "Updating Steam" or
        # "Verifying installation", Steam may disappear,
        # restart, or have no steamwebhelper yet.
        #
        # We DO NOT launch SteamVR during this.
        # ----------------------------------------------------

        if (
            not steam_pids
            or
            not webhelper_pids
        ):

            stable_since = None
            previous_steam_pids = None

            time.sleep(1)

            continue


        current_pids = tuple(
            sorted(steam_pids)
        )


        # ----------------------------------------------------
        # Steam PID changed = Steam restarted.
        #
        # Reset the stability timer.
        # ----------------------------------------------------

        if current_pids != previous_steam_pids:

            previous_steam_pids = current_pids

            stable_since = now

            log(
                "Steam detected. "
                "Waiting for it to remain stable..."
            )


        # ----------------------------------------------------
        # Steam + steamwebhelper must remain alive,
        # with the same Steam PID, for 12 seconds.
        # ----------------------------------------------------

        elif stable_since is not None:

            stable_time = (
                now - stable_since
            )

            if (
                stable_time
                >= STEAM_STABLE_SECONDS
            ):

                log(
                    "Steam is fully loaded and stable."
                )

                log_steam_status(force=True)

                return True


        time.sleep(1)


# ============================================================
# START STEAMVR
# ============================================================

def start_steamvr():

    if steamvr_running():

        log(
            "SteamVR already running."
        )

        return


    # --------------------------------------------------------
    # Make absolutely sure Steam exists first.
    # --------------------------------------------------------

    if not ensure_steam_started():
        return


    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Don't launch SteamVR until Steam has completely finished
    # loading/updating/restarting.
    # --------------------------------------------------------

    if not wait_for_steam_ready():
        return


    # Headset may have been switched off while waiting.
    state = headset_is_on()

    if state is not True:

        log(
            "PSVR2 is no longer ON. "
            "SteamVR launch cancelled."
        )

        return


    vrmonitor = find_vrmonitor()

    if vrmonitor is None:

        log(
            "ERROR: vrmonitor.exe could not be found."
        )

        return


    log(
        "PSVR2 ON -> Starting SteamVR directly "
        "with vrmonitor.exe"
    )

    log(
        f"Using: {vrmonitor}"
    )


    try:

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # NO steam:// URL
        #
        # NO vrstartup.exe
        #
        # This is the original direct launch method that
        # worked on this PC.
        # ----------------------------------------------------

        subprocess.Popen(
            [vrmonitor],
            cwd=os.path.dirname(
                vrmonitor
            ),
            creationflags=CREATE_NO_WINDOW
        )

        log(
            "vrmonitor.exe launched."
        )

    except Exception as e:

        log(
            f"Could not start SteamVR: {e}"
        )


# ============================================================
# STOP STEAMVR
# ============================================================

def stop_steamvr():

    # IMPORTANT:
    # Do NOT use vrmonitor://quit here.
    #
    # On this PC that global SteamVR quit path is associated
    # with Steam itself disappearing shortly afterwards.
    #
    # Instead, terminate ONLY SteamVR-owned processes.
    # steam.exe and steamwebhelper.exe are never touched.

    steamvr_processes = [
        "vrdashboard.exe",
        "vrwebhelper.exe",
        "vrmonitor.exe",
        "vrcompositor.exe",
        "vrserver.exe",
    ]

    running = [
        name for name in steamvr_processes
        if process_running(name)
    ]

    if not running:

        log(
            "SteamVR is already stopped."
        )

        return

    log(
        "PSVR2 OFF -> Closing SteamVR processes only."
    )

    log_steam_status(force=True)

    log(
        "SteamVR processes before shutdown: "
        + ", ".join(running)
    )

    # --------------------------------------------------------
    # Force-close ONLY SteamVR processes.
    #
    # We intentionally avoid SteamVR's global quit protocol,
    # because that was the path correlated with Steam exiting.
    #
    # Kill helper/UI processes first and vrserver last.
    # --------------------------------------------------------

    for process_name in steamvr_processes:

        if not process_running(process_name):
            continue

        log(
            f"Closing SteamVR process: {process_name}"
        )

        try:

            subprocess.run(
                [
                    "taskkill",
                    "/F",
                    "/IM",
                    process_name
                ],
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW,
                timeout=10
            )

        except Exception as e:

            log(
                f"Could not close {process_name}: {e}"
            )


    # --------------------------------------------------------
    # Wait only as long as necessary, up to 3 seconds.
    # --------------------------------------------------------

    deadline = time.monotonic() + 3.0
    remaining = []

    while time.monotonic() < deadline:

        remaining = [
            name for name in steamvr_processes
            if process_running(name)
        ]

        if not remaining:
            break

        time.sleep(0.2)

    if remaining:

        log(
            "WARNING: SteamVR processes still running: "
            + ", ".join(remaining)
        )

    else:

        log(
            "SteamVR processes closed."
        )

    # Critical diagnostic:
    # Steam itself should still have the SAME PID.
    log_steam_status(force=True)


# ============================================================
# MAIN LOOP
# ============================================================

log("")
log(
    "=================================================="
)
log(
    "PSVR2 SteamVR launcher started"
)
log(
    "=================================================="
)

log(
    "Waiting for headset..."
)


confirmed_state = False

candidate_state = None

candidate_since = time.monotonic()

session_armed = False


while True:

    try:

        raw_state = headset_is_on()

        now = time.monotonic()


        # Failed reading -> ignore it.
        if raw_state is None:

            time.sleep(
                CHECK_INTERVAL
            )

            continue


        # ----------------------------------------------------
        # Candidate state changed
        # ----------------------------------------------------

        if raw_state != candidate_state:

            candidate_state = raw_state

            candidate_since = now

            if candidate_state:

                log(
                    "PSVR2 raw state -> ON"
                )

            else:

                log(
                    "PSVR2 raw state -> OFF"
                )


        # ----------------------------------------------------
        # Debounce time
        # ----------------------------------------------------

        if candidate_state:

            required_time = (
                ON_STABLE_SECONDS
            )

        else:

            required_time = (
                OFF_STABLE_SECONDS
            )


        stable_for = (
            now - candidate_since
        )


        # ----------------------------------------------------
        # Confirm state
        # ----------------------------------------------------

        if (
            candidate_state
            != confirmed_state
            and
            stable_for
            >= required_time
        ):

            confirmed_state = (
                candidate_state
            )


            # =================================================
            # PSVR2 ON
            # =================================================

            if confirmed_state:

                log(
                    "PSVR2 CONFIRMED ON"
                )

                session_armed = True

                start_steamvr()


            # =================================================
            # PSVR2 OFF
            # =================================================

            else:

                log(
                    "PSVR2 CONFIRMED OFF"
                )

                if session_armed:

                    stop_steamvr()

                    session_armed = False

                else:

                    log(
                        "OFF ignored because "
                        "no ON session was armed."
                    )


        time.sleep(
            CHECK_INTERVAL
        )


    except KeyboardInterrupt:

        log(
            "Launcher manually stopped."
        )

        break


    except Exception as e:

        log(
            f"Unexpected error: {e}"
        )

        time.sleep(2)
