#!/usr/bin/env python3
"""Smoke test for the Windows frontend; run on a Windows desktop (CI uses windows-latest).

    python packaging/windows/smoke_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from idle_garden.config import Config  # noqa: E402
from idle_garden.idle import IdleMonitor  # noqa: E402
from idle_garden.themes import detect_system_theme  # noqa: E402
from idle_garden import winscreen, winsetup  # noqa: E402

mon = IdleMonitor()
print("idle backend:", mon.name, "| idle ms:", mon.idle_ms(), "| inhibited:", mon.is_inhibited())
print("system theme:", detect_system_theme())
print("monitors:", winscreen.monitors())
print("console:", winsetup.has_console(), "| installed:", winsetup.is_installed())
assert mon.idle_ms() is not None

for theme in ("dark", "light"):
    cfg = Config(grow_minutes=0.05, theme=theme)
    daemon = winscreen.Daemon(cfg, preview=True)
    seen = {}

    def check(daemon=daemon, seen=seen):
        win = daemon.windows[0]
        seen["cells"] = len(win.garden.cells)
        seen["items"] = sum(1 for _iid, text in win.items.values() if text)
        seen["bg"] = win.canvas.cget("bg")
        daemon.hide()  # preview: closes everything and quits the loop

    daemon.root.after(4000, check)
    daemon.run()
    print(theme, seen)
    assert seen["cells"] > 50 and seen["items"] > 10, seen
print("windows smoke test passed")
