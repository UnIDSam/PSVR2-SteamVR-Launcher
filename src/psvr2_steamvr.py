import ctypes
import csv
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

import pystray
from PIL import Image


APP_VERSION = "0.2.4"
APP_NAME = "PSVR2 SteamVR Launcher"

PROJECT_URL = "https://github.com/UnIDSam/PSVR2-SteamVR-Launcher"
ISSUES_URL = PROJECT_URL + "/issues"
RELEASES_URL = PROJECT_URL + "/releases/latest"
AUTHOR_NAME = "UnIDSam"

LOG_MAX_BYTES = 1_000_000
LOG_BACKUPS = 3

PSVR2_DEVICE = r"USB\VID_054C&PID_0CDE&MI_00"
CREATE_NO_WINDOW = 0x08000000

DEFAULT_CONFIG = {
    "check_interval": 0.75,
    "on_stable_seconds": 1.0,
    "off_stable_seconds": 2.0,
    "steam_stable_seconds": 1.0,
    "steam_ready_timeout": 60.0,
    "auto_start_steam": True,
    "notifications": True,
    "detailed_logging": True,
}

APP_DATA_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "PSVR2SteamVRLauncher",
)
os.makedirs(APP_DATA_DIR, exist_ok=True)

LOG_FILE = os.path.join(APP_DATA_DIR, "psvr2_steamvr.log")
CONFIG_FILE = os.path.join(APP_DATA_DIR, "settings.json")

stop_event = threading.Event()
state_lock = threading.Lock()
config_lock = threading.Lock()
tray_icon = None

runtime_state = {
    "headset": False,
    "steamvr": False,
    "status": "Starting...",
}


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def load_config():
    config = DEFAULT_CONFIG.copy()

    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)

            if isinstance(saved, dict):
                config.update(saved)
    except Exception:
        pass

    return config


config = load_config()


def save_config():
    with config_lock:
        snapshot = dict(config)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)


def get_config(key):
    with config_lock:
        return config.get(key, DEFAULT_CONFIG[key])


def rotate_logs_if_needed():
    try:
        if not os.path.exists(LOG_FILE):
            return

        if os.path.getsize(LOG_FILE) < LOG_MAX_BYTES:
            return

        # Delete oldest backup first.
        oldest = f"{LOG_FILE}.{LOG_BACKUPS}"

        if os.path.exists(oldest):
            os.remove(oldest)

        # Shift .2 -> .3, .1 -> .2, etc.
        for index in range(LOG_BACKUPS - 1, 0, -1):
            src = f"{LOG_FILE}.{index}"
            dst = f"{LOG_FILE}.{index + 1}"

            if os.path.exists(src):
                os.replace(src, dst)

        os.replace(LOG_FILE, f"{LOG_FILE}.1")

    except Exception:
        pass


def log(message, always=False):
    if not always and not get_config("detailed_logging"):
        return

    try:
        rotate_logs_if_needed()

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\\n")

    except Exception:
        pass


def set_status(text):
    with state_lock:
        runtime_state["status"] = text

    if tray_icon is not None:
        try:
            tray_icon.title = f"{APP_NAME} - {text}"
            tray_icon.update_menu()
        except Exception:
            pass


def notify(title, message):
    if not get_config("notifications"):
        return

    if tray_icon is not None:
        try:
            tray_icon.notify(message, title)
        except Exception:
            pass


# ============================================================
# SINGLE INSTANCE
# ============================================================

# Use a properly typed Windows named mutex.
# Every version deliberately uses the SAME mutex name so an older
# launcher and a newer launcher can never run together.

from ctypes import wintypes

MUTEX_NAME = r"Local\PSVR2_SteamVR_Launcher_SingleInstance"
ERROR_ALREADY_EXISTS = 183

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

kernel32.CreateMutexW.argtypes = (
    ctypes.c_void_p,
    wintypes.BOOL,
    wintypes.LPCWSTR,
)
kernel32.CreateMutexW.restype = wintypes.HANDLE

kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL

ctypes.set_last_error(0)

mutex_handle = kernel32.CreateMutexW(
    None,
    False,
    MUTEX_NAME,
)

mutex_error = ctypes.get_last_error()

if not mutex_handle:
    log(
        f"ERROR: Could not create single-instance mutex "
        f"(Windows error {mutex_error}).",
        always=True,
    )
    sys.exit(1)

if mutex_error == ERROR_ALREADY_EXISTS:
    log(
        "Another PSVR2 SteamVR Launcher instance is already running. "
        "This copy is exiting.",
        always=True,
    )
    kernel32.CloseHandle(mutex_handle)
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
                "/NH",
            ],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
        )

        pids = []

        for row in csv.reader(io.StringIO(result.stdout)):
            if len(row) < 2:
                continue

            if row[0].lower() != process_name.lower():
                continue

            try:
                pids.append(int(row[1]))
            except ValueError:
                pass

        return pids

    except Exception as e:
        log(f"Process check failed for {process_name}: {e}", always=True)
        return []


def process_running(process_name):
    return bool(get_process_pids(process_name))


# ============================================================
# STEAM STATUS
# ============================================================

last_steam_status = None


def get_steam_status():
    steam_pids = get_process_pids("steam.exe")
    webhelper_pids = get_process_pids("steamwebhelper.exe")

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
# STEAM / STEAMVR LOCATIONS
# ============================================================

def find_steam_exe():
    possible_paths = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Steam\steam.exe"),
        os.path.expandvars(r"%ProgramFiles%\Steam\steam.exe"),
        r"C:\Steam\steam.exe",
        r"D:\Steam\steam.exe",
        r"E:\Steam\steam.exe",
        r"F:\Steam\steam.exe",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def get_steam_libraries():
    possible_roots = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Steam"),
        os.path.expandvars(r"%ProgramFiles%\Steam"),
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
        vdf = os.path.join(root, "steamapps", "libraryfolders.vdf")

        if not os.path.exists(vdf):
            continue

        try:
            with open(vdf, "r", encoding="utf-8") as f:
                content = f.read()

            matches = re.findall(r'"path"\s+"([^"]+)"', content)

            for path in matches:
                libraries.add(path.replace("\\\\", "\\"))

        except Exception as e:
            log(f"Could not read libraryfolders.vdf: {e}")

    return libraries


def find_vrmonitor():
    for library in get_steam_libraries():
        candidate = os.path.join(
            library,
            "steamapps",
            "common",
            "SteamVR",
            "bin",
            "win64",
            "vrmonitor.exe",
        )

        if os.path.exists(candidate):
            return candidate

    return None


# ============================================================
# HEADSET STATE
# ============================================================

def headset_is_on():
    command = (
        "Get-PnpDevice | "
        "Where-Object { "
        "$_.InstanceId -like '"
        + PSVR2_DEVICE
        + r"\*' -and "
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
                command,
            ],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=10,
        )

        if result.returncode != 0:
            log("PSVR2 PowerShell check failed. Ignoring reading.")
            return None

        return bool(result.stdout.strip())

    except Exception as e:
        log(f"PSVR2 detection error: {e}", always=True)
        return None


def steamvr_running():
    return process_running("vrmonitor.exe")


# ============================================================
# START STEAM / WAIT READY
# ============================================================

def ensure_steam_started():
    if process_running("steam.exe"):
        log("Steam is already running.")
        return True

    if not get_config("auto_start_steam"):
        log("Steam is not running and auto-start Steam is disabled.", always=True)
        set_status("Steam is not running")
        notify(APP_NAME, "Steam is not running.")
        return False

    steam_exe = find_steam_exe()

    if steam_exe is None:
        log("ERROR: steam.exe could not be found.", always=True)
        set_status("Steam not found")
        notify(APP_NAME, "Steam could not be found.")
        return False

    log("Steam is not running.")
    log("Starting Steam and waiting for it to become ready.")

    try:
        subprocess.Popen(
            [steam_exe, "-silent"],
            cwd=os.path.dirname(steam_exe),
            creationflags=CREATE_NO_WINDOW,
        )
        return True

    except Exception as e:
        log(f"Could not start Steam: {e}", always=True)
        set_status("Steam failed to start")
        return False


def wait_for_steam_ready(cancel_if_headset_off=True):
    log("Waiting for Steam to be fully ready...")
    log_steam_status(force=True)

    started_waiting = time.monotonic()
    stable_since = None
    previous_steam_pids = None

    while not stop_event.is_set():
        now = time.monotonic()
        log_steam_status()

        if cancel_if_headset_off:
            headset_state = headset_is_on()

            if headset_state is False:
                log("PSVR2 turned OFF while waiting for Steam. Launch cancelled.")
                return False

        if now - started_waiting >= get_config("steam_ready_timeout"):
            log("Steam did not become ready before timeout.", always=True)
            set_status("Steam ready timeout")
            return False

        steam_pids = get_process_pids("steam.exe")
        webhelper_pids = get_process_pids("steamwebhelper.exe")

        if not steam_pids or not webhelper_pids:
            stable_since = None
            previous_steam_pids = None
            time.sleep(0.35)
            continue

        current_pids = tuple(sorted(steam_pids))

        if current_pids != previous_steam_pids:
            previous_steam_pids = current_pids
            stable_since = now
            log("Steam detected. Waiting briefly for stability...")

        elif stable_since is not None:
            if now - stable_since >= get_config("steam_stable_seconds"):
                log("Steam is fully loaded and stable.")
                log_steam_status(force=True)
                return True

        time.sleep(0.25)

    return False


# ============================================================
# START / STOP STEAMVR
# ============================================================

def start_steamvr(manual=False):
    if steamvr_running():
        set_status("SteamVR running")
        log("SteamVR already running.")
        return

    set_status("Starting SteamVR...")

    if not ensure_steam_started():
        return

    if not wait_for_steam_ready(cancel_if_headset_off=not manual):
        return

    if not manual:
        state = headset_is_on()

        if state is not True:
            log("PSVR2 is no longer ON. SteamVR launch cancelled.")
            set_status("Headset off")
            return

    vrmonitor = find_vrmonitor()

    if vrmonitor is None:
        log("ERROR: vrmonitor.exe could not be found.", always=True)
        set_status("SteamVR not found")
        notify(APP_NAME, "SteamVR could not be found.")
        return

    log("Starting SteamVR directly with vrmonitor.exe")
    log(f"Using: {vrmonitor}")

    try:
        subprocess.Popen(
            [vrmonitor],
            cwd=os.path.dirname(vrmonitor),
            creationflags=CREATE_NO_WINDOW,
        )

        log("vrmonitor.exe launched.")
        set_status("SteamVR starting")
        notify(APP_NAME, "SteamVR is starting.")

    except Exception as e:
        log(f"Could not start SteamVR: {e}", always=True)
        set_status("SteamVR start failed")


def stop_steamvr(manual=False):
    # Kill only SteamVR-owned processes.
    # Never touch steam.exe or steamwebhelper.exe.
    #
    # vrserver.exe is killed first because it can keep/restart
    # the rest of the SteamVR process set.

    steamvr_processes = [
        "vrserver.exe",
        "vrmonitor.exe",
        "vrcompositor.exe",
        "vrdashboard.exe",
        "vrwebhelper.exe",
    ]

    running = [
        name for name in steamvr_processes
        if process_running(name)
    ]

    if not running:
        log("SteamVR is already stopped.")
        set_status("SteamVR stopped")
        return

    log("Closing SteamVR processes only.")
    log_steam_status(force=True)
    log("SteamVR processes before shutdown: " + ", ".join(running))
    set_status("Stopping SteamVR...")

    deadline = time.monotonic() + 5.0
    pass_number = 0
    remaining = running[:]

    while remaining and time.monotonic() < deadline:
        pass_number += 1

        log(
            f"SteamVR shutdown pass {pass_number}: "
            + ", ".join(remaining)
        )

        for process_name in steamvr_processes:
            if process_name not in remaining:
                continue

            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", process_name],
                    capture_output=True,
                    text=True,
                    creationflags=CREATE_NO_WINDOW,
                    timeout=5,
                )
            except Exception as e:
                log(
                    f"Could not close {process_name}: {e}",
                    always=True,
                )

        # Give Windows a brief moment to tear the processes down,
        # then check again. If one respawned, the next pass catches it.
        time.sleep(0.25)

        remaining = [
            name for name in steamvr_processes
            if process_running(name)
        ]

    if remaining:
        log(
            "WARNING: SteamVR processes still running after retries: "
            + ", ".join(remaining),
            always=True,
        )
        set_status("SteamVR partially stopped")
    else:
        log(
            f"SteamVR processes closed after {pass_number} pass(es)."
        )
        set_status("SteamVR stopped")
        notify(APP_NAME, "SteamVR stopped.")

    # Confirm Steam itself stayed alive.
    log_steam_status(force=True)



# ============================================================
# SUPPORT / LOG HELPERS
# ============================================================

def clear_logs():
    deleted = 0

    try:
        candidates = [LOG_FILE] + [
            f"{LOG_FILE}.{index}"
            for index in range(1, LOG_BACKUPS + 1)
        ]

        for path in candidates:
            if os.path.exists(path):
                os.remove(path)
                deleted += 1

        Path(LOG_FILE).touch()
        log("Logs cleared.", always=True)

        def show_result():
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo(
                APP_NAME,
                f"Logs cleared.\\n\\nDeleted {deleted} old log file(s)."
            )
            root.destroy()

        threading.Thread(target=show_result, daemon=True).start()

    except Exception as e:
        log(f"Could not clear logs: {e}", always=True)


def open_project():
    webbrowser.open(PROJECT_URL)


def report_bug():
    webbrowser.open(ISSUES_URL)


def check_latest_release():
    webbrowser.open(RELEASES_URL)


# ============================================================
# SETTINGS WINDOW
# ============================================================

settings_window_lock = threading.Lock()
settings_window_open = False


def open_settings():
    global settings_window_open

    with settings_window_lock:
        if settings_window_open:
            return
        settings_window_open = True

    def run_window():
        global settings_window_open

        try:
            root = tk.Tk()
            root.title(f"{APP_NAME} Settings")
            root.resizable(False, False)

            try:
                root.iconbitmap(resource_path(os.path.join("assets", "icon.ico")))
            except Exception:
                pass

            frame = ttk.Frame(root, padding=16)
            frame.grid(row=0, column=0, sticky="nsew")

            ttk.Label(
                frame,
                text=f"{APP_NAME} v{APP_VERSION}",
                font=("Segoe UI", 12, "bold"),
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

            fields = [
                ("PSVR2 ON delay (seconds)", "on_stable_seconds"),
                ("PSVR2 OFF delay (seconds)", "off_stable_seconds"),
                ("Steam ready delay (seconds)", "steam_stable_seconds"),
                ("Polling interval (seconds)", "check_interval"),
            ]

            vars_map = {}

            for idx, (label, key) in enumerate(fields, start=1):
                ttk.Label(frame, text=label).grid(
                    row=idx, column=0, sticky="w", padx=(0, 12), pady=4
                )

                var = tk.StringVar(value=str(get_config(key)))
                vars_map[key] = var

                ttk.Entry(frame, textvariable=var, width=10).grid(
                    row=idx, column=1, sticky="e", pady=4
                )

            auto_start_var = tk.BooleanVar(value=get_config("auto_start_steam"))
            notifications_var = tk.BooleanVar(value=get_config("notifications"))
            logging_var = tk.BooleanVar(value=get_config("detailed_logging"))

            base_row = 1 + len(fields)

            ttk.Checkbutton(
                frame,
                text="Start Steam automatically if needed",
                variable=auto_start_var,
            ).grid(row=base_row, column=0, columnspan=2, sticky="w", pady=(10, 2))

            ttk.Checkbutton(
                frame,
                text="Show tray notifications",
                variable=notifications_var,
            ).grid(row=base_row + 1, column=0, columnspan=2, sticky="w", pady=2)

            ttk.Checkbutton(
                frame,
                text="Detailed logging",
                variable=logging_var,
            ).grid(row=base_row + 2, column=0, columnspan=2, sticky="w", pady=2)

            ttk.Separator(frame).grid(
                row=base_row + 3,
                column=0,
                columnspan=2,
                sticky="ew",
                pady=12,
            )

            def save():
                try:
                    updates = {}

                    for key, var in vars_map.items():
                        value = float(var.get())

                        if value < 0.1 or value > 30:
                            raise ValueError

                        updates[key] = value

                    with config_lock:
                        config.update(updates)
                        config["auto_start_steam"] = auto_start_var.get()
                        config["notifications"] = notifications_var.get()
                        config["detailed_logging"] = logging_var.get()

                    save_config()
                    log("Settings saved.", always=True)
                    messagebox.showinfo(APP_NAME, "Settings saved.")

                except ValueError:
                    messagebox.showerror(
                        APP_NAME,
                        "Timing values must be numbers between 0.1 and 30 seconds.",
                    )

            def defaults():
                with config_lock:
                    config.update(DEFAULT_CONFIG)
                save_config()
                root.destroy()
                with settings_window_lock:
                    settings_window_open = False
                open_settings()

            buttons = ttk.Frame(frame)
            buttons.grid(
                row=base_row + 4,
                column=0,
                columnspan=2,
                sticky="e",
            )

            ttk.Button(buttons, text="Defaults", command=defaults).pack(
                side="left", padx=(0, 8)
            )
            ttk.Button(buttons, text="Save", command=save).pack(
                side="left", padx=(0, 8)
            )
            ttk.Button(buttons, text="Close", command=root.destroy).pack(
                side="left"
            )

            def on_close():
                root.destroy()

            root.protocol("WM_DELETE_WINDOW", on_close)
            root.mainloop()

        finally:
            with settings_window_lock:
                settings_window_open = False

    threading.Thread(target=run_window, daemon=True).start()


# ============================================================
# OPEN HELPERS
# ============================================================

def open_log():
    try:
        if not os.path.exists(LOG_FILE):
            Path(LOG_FILE).touch()

        os.startfile(LOG_FILE)
    except Exception as e:
        log(f"Could not open log file: {e}", always=True)


def open_install_folder():
    try:
        os.startfile(APP_DATA_DIR)
    except Exception as e:
        log(f"Could not open install folder: {e}", always=True)


def show_about():
    def run_about():
        root = tk.Tk()
        root.withdraw()

        messagebox.showinfo(
            APP_NAME,
            f"{APP_NAME}\n"
            f"Version {APP_VERSION}\n"
            f"Author: {AUTHOR_NAME}\n\n"
            "Automatically starts and stops SteamVR with PSVR2.\n"
            "Steam itself is never force-closed.\n\n"
            f"Project / Support:\n{PROJECT_URL}\n\n"
            "Not affiliated with Sony, Valve, PlayStation, or Steam.",
        )

        root.destroy()

    threading.Thread(target=run_about, daemon=True).start()


# ============================================================
# WATCHER
# ============================================================

def watcher_loop():
    log("")
    log("==================================================", always=True)
    log(f"{APP_NAME} v{APP_VERSION} started", always=True)
    log("==================================================", always=True)
    log("Waiting for headset...", always=True)

    confirmed_state = False
    candidate_state = None
    candidate_since = time.monotonic()
    session_armed = False

    while not stop_event.is_set():
        try:
            raw_state = headset_is_on()
            now = time.monotonic()

            if raw_state is None:
                time.sleep(get_config("check_interval"))
                continue

            if raw_state != candidate_state:
                candidate_state = raw_state
                candidate_since = now

                if candidate_state:
                    log("PSVR2 raw state -> ON")

                    steam_pids_at_on = get_process_pids("steam.exe")

                    if steam_pids_at_on:
                        log(
                            "STEAM AT PSVR2 ON -> "
                            f"steam.exe PID(s): {steam_pids_at_on}"
                        )
                    else:
                        log(
                            "STEAM AT PSVR2 ON -> NOT RUNNING"
                        )

                    set_status("PSVR2 detected")
                else:
                    log("PSVR2 raw state -> OFF")
                    set_status("PSVR2 off")

            required_time = (
                get_config("on_stable_seconds")
                if candidate_state
                else get_config("off_stable_seconds")
            )

            stable_for = now - candidate_since

            if (
                candidate_state != confirmed_state
                and stable_for >= required_time
            ):
                confirmed_state = candidate_state

                with state_lock:
                    runtime_state["headset"] = confirmed_state

                if confirmed_state:
                    log("PSVR2 CONFIRMED ON")
                    session_armed = True
                    start_steamvr()

                else:
                    log("PSVR2 CONFIRMED OFF")

                    if session_armed:
                        stop_steamvr()
                        session_armed = False

                    else:
                        log("OFF ignored because no ON session was armed.")

            with state_lock:
                runtime_state["steamvr"] = steamvr_running()

            time.sleep(get_config("check_interval"))

        except Exception as e:
            log(f"Unexpected watcher error: {e}", always=True)
            time.sleep(1)


# ============================================================
# TRAY
# ============================================================

def tray_status_text(_item=None):
    with state_lock:
        return f"Status: {runtime_state['status']}"


def tray_start(_icon=None, _item=None):
    threading.Thread(
        target=start_steamvr,
        kwargs={"manual": True},
        daemon=True,
    ).start()


def tray_stop(_icon=None, _item=None):
    threading.Thread(
        target=stop_steamvr,
        kwargs={"manual": True},
        daemon=True,
    ).start()


def tray_exit(icon, _item=None):
    log("Exit requested from tray.", always=True)
    stop_event.set()

    try:
        icon.stop()
    except Exception:
        pass


def main():
    global tray_icon

    image = Image.open(
        resource_path(os.path.join("assets", "icon.png"))
    )

    menu = pystray.Menu(
        pystray.MenuItem(tray_status_text, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start SteamVR now", tray_start),
        pystray.MenuItem("Stop SteamVR now", tray_stop),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Settings", lambda *_: open_settings()),
        pystray.MenuItem("Open log file", lambda *_: open_log()),
        pystray.MenuItem("Clear logs", lambda *_: clear_logs()),
        pystray.MenuItem("Open install folder", lambda *_: open_install_folder()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Project / Support", lambda *_: open_project()),
        pystray.MenuItem("Report a bug", lambda *_: report_bug()),
        pystray.MenuItem("Check latest release", lambda *_: check_latest_release()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("About", lambda *_: show_about()),
        pystray.MenuItem("Exit", tray_exit),
    )

    tray_icon = pystray.Icon(
        "PSVR2SteamVRLauncher",
        image,
        APP_NAME,
        menu,
    )

    threading.Thread(target=watcher_loop, daemon=True).start()

    set_status("Waiting for PSVR2")
    tray_icon.run()


if __name__ == "__main__":
    main()
