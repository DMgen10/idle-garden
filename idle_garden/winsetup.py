"""Windows integration: one running copy, autostart, Start menu, uninstall.

Installing means:

* the program is copied to ``%LOCALAPPDATA%\\Programs\\Idle Garden`` (the .exe,
  or nothing when running from Python sources),
* it is started at every login (``HKCU\\...\\Run``, no admin rights needed),
* "Idle Garden" and "Uninstall Idle Garden" appear in the Start menu.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "Idle Garden"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "IdleGarden"
EXE_NAME = "IdleGarden.exe"

LOCAL = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
INSTALL_DIR = LOCAL / "Programs" / APP_NAME
STATE_DIR = LOCAL / "idle-garden"
PID_FILE = STATE_DIR / "idle-garden.pid"
START_MENU = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) \
    / "Microsoft" / "Windows" / "Start Menu" / "Programs"

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
ERROR_ALREADY_EXISTS = 183

FROZEN = bool(getattr(sys, "frozen", False))

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.GetConsoleWindow.restype = ctypes.c_void_p
_k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
_k32.CreateMutexW.restype = ctypes.c_void_p
_k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
_k32.OpenProcess.restype = ctypes.c_void_p
_k32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
_k32.CloseHandle.argtypes = [ctypes.c_void_p]

# decided once at start-up: double-clicked .exe / pythonw have no console
_CONSOLE = sys.stdout is not None and bool(_k32.GetConsoleWindow())


# ------------------------------------------------------------------ output

def has_console() -> bool:
    return _CONSOLE


def message(text: str, error: bool = False) -> None:
    """print() in a console, a message box when started by double-click."""
    if has_console():
        print(text, file=sys.stderr if error else sys.stdout)
    else:
        ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, 0x10 if error else 0x40)


# --------------------------------------------------------- single instance

_mutex = None


def single_instance() -> bool:
    """False if another background copy is already running."""
    global _mutex
    _mutex = _k32.CreateMutexW(None, False, "Local\\idle-garden-daemon")
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return False
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))
    return True


def stop_running() -> bool:
    try:
        pid = int(PID_FILE.read_text().strip())
    except (OSError, ValueError):
        return False
    if pid == os.getpid():
        return False
    PROCESS_TERMINATE, SYNCHRONIZE = 0x0001, 0x00100000
    k32 = _k32
    handle = k32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, pid)
    if not handle:
        return False
    try:
        ok = bool(k32.TerminateProcess(handle, 0))
        k32.WaitForSingleObject(handle, 3000)
    finally:
        k32.CloseHandle(handle)
    try:
        PID_FILE.unlink()
    except OSError:
        pass
    return ok


# ---------------------------------------------------------------- commands

def _pythonw() -> str:
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate if candidate.exists() else exe)


def launch_command(*args: str, installed: bool = True) -> list[str]:
    """How to start the program in the background (no console window)."""
    if FROZEN:
        exe = INSTALL_DIR / EXE_NAME if installed else Path(sys.executable)
        return [str(exe), *args]
    src = str(Path(__file__).resolve().parent.parent)
    code = f"import sys; sys.path.insert(0, {src!r}); from idle_garden.__main__ import main; sys.exit(main())"
    return [_pythonw(), "-c", code, *args]


def start_detached(*args: str, installed: bool = True) -> None:
    subprocess.Popen(  # noqa: S603
        launch_command(*args, installed=installed),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW, close_fds=True,
    )


def _quote(parts: list[str]) -> str:
    return subprocess.list2cmdline(parts)


def _shortcut(path: Path, cmd: list[str], description: str) -> None:
    """Create a .lnk through the WScript.Shell COM object (via PowerShell)."""
    def ps(s: str) -> str:
        return "'" + s.replace("'", "''") + "'"

    target, args = cmd[0], _quote(cmd[1:])
    script = (
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut({ps(str(path))}); "
        f"$s.TargetPath = {ps(target)}; $s.Arguments = {ps(args)}; "
        f"$s.Description = {ps(description)}; "
        + (f"$s.IconLocation = {ps(target)}; " if FROZEN else "")
        + "$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],  # noqa: S603,S607
                   capture_output=True, creationflags=CREATE_NO_WINDOW, timeout=30, check=False)


# ---------------------------------------------------------------- autostart

def autostart_command() -> str | None:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, RUN_VALUE)[0]
    except OSError:
        return None


def is_installed() -> bool:
    return autostart_command() is not None


def _set_autostart(cmd: list[str] | None) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if cmd is None:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except OSError:
                pass
        else:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, _quote(cmd))


# ----------------------------------------------------------- install/remove

def install() -> str:
    stop_running()
    if FROZEN:
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        src, dst = Path(sys.executable).resolve(), (INSTALL_DIR / EXE_NAME).resolve()
        if src != dst:
            shutil.copy2(src, dst)
    _set_autostart(launch_command())
    START_MENU.mkdir(parents=True, exist_ok=True)
    _shortcut(START_MENU / f"{APP_NAME}.lnk", launch_command("--preview"),
              "Watch the ASCII tree grow now (move the mouse to close)")
    _shortcut(START_MENU / f"Uninstall {APP_NAME}.lnk", launch_command("--uninstall"),
              "Remove Idle Garden")
    start_detached()
    return (f"{APP_NAME} is installed and running.\n\n"
            "Leave the computer alone for 2 minutes and a tree starts to grow.\n"
            "It starts by itself after every login.\n\n"
            f"Start menu → {APP_NAME} shows it right now.")


def uninstall() -> str:
    stop_running()
    _set_autostart(None)
    for name in (f"{APP_NAME}.lnk", f"Uninstall {APP_NAME}.lnk"):
        try:
            (START_MENU / name).unlink()
        except OSError:
            pass
    shutil.rmtree(STATE_DIR, ignore_errors=True)
    if INSTALL_DIR.exists():
        # a running .exe cannot delete itself: remove the folder once this process exits
        folder = str(INSTALL_DIR).replace("'", "''")
        script = (f"Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue; "
                  f"Remove-Item -LiteralPath '{folder}' -Recurse -Force -ErrorAction SilentlyContinue")
        subprocess.Popen(  # noqa: S603,S607
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW, close_fds=True,
        )
    return f"{APP_NAME} has been removed. Your settings in %APPDATA%\\idle-garden were kept."
