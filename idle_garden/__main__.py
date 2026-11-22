"""Command line entry point: ``python3 -m idle_garden`` / ``idle-garden``."""

from __future__ import annotations

import argparse
import fcntl
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from .config import CONFIG_FILE, load_config, write_default_config


LOCK_PATH = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / f"idle-garden-{os.getuid()}.lock"


def _single_instance() -> object | None:
    """Return a lock handle, or None if another daemon is already running."""
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
    subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "idle_garden"],
        cwd=str(Path(__file__).resolve().parent.parent),
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def main(argv: list[str] | None = None) -> int:
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
    p.add_argument("-t", "--timeout", type=float, help="seconds of inactivity before the tree appears")
    p.add_argument("-g", "--grow-minutes", type=float,
                   help="minutes until the tree fills the screen (default 40)")
    p.add_argument("--font-size", type=float, help="ASCII font size in pixels (default 18)")
    p.add_argument("-V", "--version", action="version", version=f"idle-garden {__version__}")
    args = p.parse_args(argv)

    if args.stop or args.restart:
        stopped = _stop_running()
        if args.restart:
            _start_detached()
            print("idle-garden restarted.")
        else:
            print("idle-garden stopped." if stopped else "idle-garden was not running.")
        return 0

    if args.edit_config:
        print(write_default_config())
        return 0

    cfg = load_config()
    for name in ("timeout", "grow_minutes", "font_size"):
        value = getattr(args, name)
        if value is not None:
            setattr(cfg, name, value)

    if args.terminal:
        from .terminal import run_terminal

        run_terminal(cfg)
        return 0

    if args.check:
        from .idle import IdleMonitor

        try:
            mon = IdleMonitor()
        except RuntimeError as exc:
            print(exc)
            return 1
        print(f"backend:   {mon.name}")
        print(f"idle now:  {mon.idle_ms()} ms")
        print(f"inhibited: {mon.is_inhibited()}")
        print(f"config:    {CONFIG_FILE} ({'found' if CONFIG_FILE.exists() else 'not created, using defaults'})")
        return 0

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
            print("idle-garden is already running.", file=sys.stderr)
            return 0
    try:
        Daemon(cfg, preview=args.preview).run()
    except RuntimeError as exc:
        print(f"idle-garden: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
