"""Command line entry point: ``python3 -m idle_garden`` / ``idle-garden`` / ``IdleGarden.exe``."""

from __future__ import annotations

import argparse
import io
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from .config import CONFIG_FILE, load_config, write_default_config

WINDOWS = sys.platform == "win32"

if WINDOWS:
    from . import winsetup
else:
    import fcntl

    LOCK_PATH = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / f"idle-garden-{os.getuid()}.lock"


# ------------------------------------------------------------- Linux helpers

def _single_instance() -> object | None:
    """Return a lock handle, or None if another daemon is already running."""
    if WINDOWS:
        return True if winsetup.single_instance() else None
    handle = open(LOCK_PATH, "a+")  # noqa: SIM115 - kept open for process lifetime
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    handle.seek(0)
    handle.truncate()
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def _stop_running() -> bool:
    if WINDOWS:
        return winsetup.stop_running()
    try:
        pid = int(LOCK_PATH.read_text().strip())
    except (OSError, ValueError):
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    for _ in range(30):  # wait up to 3 s for it to exit
        time.sleep(0.1)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
    return True


def _start_detached() -> None:
    if WINDOWS:
        winsetup.start_detached(installed=winsetup.FROZEN and winsetup.is_installed())
        return
    subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "idle_garden"],
        cwd=str(Path(__file__).resolve().parent.parent),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _say(text: str, error: bool = False) -> None:
    if WINDOWS:
        winsetup.message(text, error)
    else:
        print(text, file=sys.stderr if error else sys.stdout)


# ---------------------------------------------------------------------- main

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="idle-garden",
        description="An ASCII tree slowly grows over your screen while you are away.",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--preview", action="store_true", help="show the tree right now (fullscreen)")
    mode.add_argument("--terminal", action="store_true", help="grow a tree inside this terminal")
    mode.add_argument("--check", action="store_true", help="check idle detection on this desktop and exit")
    mode.add_argument("--stop", action="store_true", help="stop the running background app")
    mode.add_argument("--restart", action="store_true", help="restart the background app (after editing config)")
    mode.add_argument("--edit-config", action="store_true", help="create the config file and print its path")
    if WINDOWS:
        mode.add_argument("--install", action="store_true",
                          help="start with Windows and add Start menu shortcuts")
        mode.add_argument("--uninstall", action="store_true", help="undo --install")
    p.add_argument("-t", "--timeout", type=float, help="seconds of inactivity before the tree appears")
    p.add_argument("-g", "--grow-minutes", type=float,
                   help="minutes until the tree fills the screen (default 40)")
    p.add_argument("--theme", choices=("auto", "dark", "light"),
                   help="colour theme (default: auto, follows the system)")
    p.add_argument("--season", choices=("auto", "spring", "summer", "autumn", "winter"),
                   help="season of the garden (default: auto, from today's date)")
    p.add_argument("--no-animals", dest="animals", action="store_false", default=None,
                   help="no birds or butterflies")
    p.add_argument("--font-size", type=float, help="ASCII font size in pixels (default 18)")
    p.add_argument("-V", "--version", action="version", version=f"idle-garden {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if WINDOWS and not winsetup.has_console():
        # double-clicked .exe: no console, so show --help / errors in a window
        buf = io.StringIO()
        sys.stdout = sys.stderr = buf
        try:
            args = _parser().parse_args(argv)
        except SystemExit as exc:
            winsetup.message(buf.getvalue().strip() or "idle-garden", error=bool(exc.code))
            return int(exc.code or 0)
    else:
        args = _parser().parse_args(argv)

    if WINDOWS and args.install:
        _say(winsetup.install())
        return 0
    if WINDOWS and args.uninstall:
        _say(winsetup.uninstall())
        return 0

    if args.stop or args.restart:
        stopped = _stop_running()
        if args.restart:
            _start_detached()
            _say("idle-garden restarted.")
        else:
            _say("idle-garden stopped." if stopped else "idle-garden was not running.")
        return 0

    if args.edit_config:
        path = write_default_config()
        if WINDOWS and not winsetup.has_console():
            os.startfile(str(path))  # noqa: S606 - opens it in Notepad
        else:
            print(path)
        return 0

    cfg = load_config()
    for name in ("timeout", "grow_minutes", "font_size", "theme", "season", "animals"):
        value = getattr(args, name)
        if value is not None:
            setattr(cfg, name, value)

    if args.terminal:
        from .terminal import run_terminal

        run_terminal(cfg)
        return 0

    if args.check:
        from .idle import IdleMonitor
        from .nature import detect_hemisphere, resolve_season
        from .themes import detect_system_theme, resolve_theme

        try:
            mon = IdleMonitor()
        except RuntimeError as exc:
            _say(str(exc), error=True)
            return 1
        _say("\n".join((
            f"backend:   {mon.name}",
            f"idle now:  {mon.idle_ms()} ms",
            f"inhibited: {mon.is_inhibited()}",
            f"theme:     {resolve_theme(cfg.theme)} (setting: {cfg.theme}, system: {detect_system_theme() or 'unknown'})",
            f"season:    {resolve_season(cfg.season, cfg.hemisphere)[0]} (setting: {cfg.season}, "
            f"hemisphere: {cfg.hemisphere if cfg.hemisphere in ('north', 'south') else detect_hemisphere()})",
            f"config:    {CONFIG_FILE} ({'found' if CONFIG_FILE.exists() else 'not created, using defaults'})",
        )))
        return 0

    if WINDOWS:
        from .winscreen import Daemon

        if not args.preview and winsetup.FROZEN and not winsetup.is_installed():
            # first double-click on the downloaded .exe: set everything up
            _say(winsetup.install())
            return 0
    else:
        try:
            from .screen import Daemon
        except (ImportError, ValueError) as exc:
            print(
                f"idle-garden: GTK 3 for Python is missing ({exc}).\n"
                "Install it with:  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0",
                file=sys.stderr,
            )
            return 1

    if not args.preview:
        lock = _single_instance()
        if lock is None:
            _say("Idle Garden is already running.\n"
                 "Leave the computer alone for a while and the tree will grow.", error=False)
            return 0
    try:
        Daemon(cfg, preview=args.preview).run()
    except RuntimeError as exc:
        _say(f"idle-garden: {exc}", error=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
