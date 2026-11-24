"""Windows frontend: borderless topmost Tk windows on every monitor.

Uses only the standard library (tkinter + ctypes), so it runs on any
Python for Windows and freezes into a single .exe with PyInstaller.
"""

from __future__ import annotations

import ctypes
import time
import tkinter as tk
import tkinter.font as tkfont
from ctypes import wintypes

from .config import Config
from .nature import LivingGarden, garden_options
from .themes import theme_colors

MOTION_THRESHOLD = 10
GRACE_SECONDS = 0.8

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

ES_CONTINUOUS = 0x80000000
ES_DISPLAY_REQUIRED = 0x00000002

kernel32.SetThreadExecutionState.argtypes = [wintypes.DWORD]
kernel32.SetThreadExecutionState.restype = wintypes.DWORD


def _dpi_aware() -> None:
    """Work in real pixels, otherwise Windows scales (and blurs) the window."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor
    except (AttributeError, OSError):
        try:
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


_MonitorEnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                      ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                       _MonitorEnumProc, wintypes.LPARAM]
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(_MonitorInfo)]


def monitors() -> list[tuple[int, int, int, int, float]]:
    """(x, y, width, height, scale) of every monitor, in physical pixels."""
    found = []

    def callback(hmon, _hdc, _rect, _data):
        info = _MonitorInfo()
        info.cbSize = ctypes.sizeof(_MonitorInfo)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            r = info.rcMonitor
            scale = 1.0
            try:
                dx, dy = wintypes.UINT(), wintypes.UINT()
                shcore = ctypes.windll.shcore
                shcore.GetDpiForMonitor.argtypes = [wintypes.HMONITOR, ctypes.c_int,
                                                    ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT)]
                if shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dx), ctypes.byref(dy)) == 0:
                    scale = dx.value / 96
            except (AttributeError, OSError):
                pass
            found.append((r.left, r.top, r.right - r.left, r.bottom - r.top, scale))
        return 1

    user32.EnumDisplayMonitors(None, None, _MonitorEnumProc(callback), 0)
    if not found:
        found.append((0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1), 1.0))
    return found


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(rgb)


class GardenWindow:
    def __init__(self, root: tk.Tk, cfg: Config, rect, on_activity, palette, background):
        x, y, w, h, scale = rect
        self.cfg = cfg
        self.on_activity = on_activity
        self.palette = {name: _hex(rgb) for name, rgb in palette.items()}
        self.shown_at = time.monotonic()
        self.last_tick = self.shown_at
        self.pointer_origin = None
        self.version = -1
        self.items: dict[tuple[str, int], tuple[int, str]] = {}

        bg = _hex(background)
        top = self.top = tk.Toplevel(root, bg=bg, cursor="none")
        top.overrideredirect(True)
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.attributes("-topmost", True)
        canvas = self.canvas = tk.Canvas(top, width=w, height=h, bg=bg, cursor="none",
                                         highlightthickness=0, borderwidth=0)
        canvas.pack(fill="both", expand=True)

        size = max(6, int(round(cfg.font_size * scale)))
        self.font = tkfont.Font(root=root, family=cfg.font_family, size=-size, weight="bold")
        self.cell_w = max(1, self.font.measure("M"))
        self.cell_h = max(1, self.font.metrics("linespace"))
        cols, rows = max(20, w // self.cell_w), max(12, h // self.cell_h)
        self.garden = LivingGarden(cols, rows, cfg.grow_minutes, **garden_options(cfg))
        self.ox = (w - self.garden.grid_cols * self.cell_w) // 2
        self.oy = (h - self.garden.grid_rows * self.cell_h) // 2

        for seq in ("<Key>", "<Button>", "<MouseWheel>"):
            top.bind(seq, self._wake)
        top.bind("<Motion>", self._on_motion)
        top.protocol("WM_DELETE_WINDOW", lambda: None)  # only input closes us
        top.lift()
        top.focus_force()
        self._draw()

    # -- input ------------------------------------------------------------- #

    def _wake(self, _event=None):
        if time.monotonic() - self.shown_at > 0.15:
            self.on_activity()

    def _on_motion(self, event):
        if time.monotonic() - self.shown_at < GRACE_SECONDS or self.pointer_origin is None:
            self.pointer_origin = (event.x_root, event.y_root)
            return
        ox, oy = self.pointer_origin
        if abs(event.x_root - ox) + abs(event.y_root - oy) > MOTION_THRESHOLD:
            self.on_activity()

    # -- animation --------------------------------------------------------- #

    def tick(self):
        now = time.monotonic()
        dt, self.last_tick = now - self.last_tick, now
        self.garden.update(min(dt, 0.5))
        if self.garden.version != self.version:
            self._draw()

    def _draw(self):
        self.version = self.garden.version
        gcols = self.garden.grid_cols
        # one text item per (colour, row), like the GTK version
        lines: dict[tuple[str, int], list[str]] = {}
        for (x, y), (ch, color) in self.garden.cells.items():
            line = lines.get((color, y))
            if line is None:
                line = lines[(color, y)] = [" "] * gcols
            line[x] = ch
        for key, chars in lines.items():
            text = "".join(chars).rstrip()
            item = self.items.get(key)
            if item is None:
                color, y = key
                iid = self.canvas.create_text(
                    self.ox, self.oy + y * self.cell_h, text=text, anchor="nw",
                    font=self.font, fill=self.palette.get(color, "#808080"))
                self.items[key] = (iid, text)
            elif item[1] != text:
                self.canvas.itemconfigure(item[0], text=text)
                self.items[key] = (item[0], text)
        for key, (iid, text) in list(self.items.items()):
            if key not in lines and text:
                self.canvas.itemconfigure(iid, text="")
                self.items[key] = (iid, "")

    def close(self):
        self.top.destroy()


class Daemon:
    """Watches idle time and shows/hides the garden on every monitor."""

    POLL_IDLE_MS = 1000
    POLL_SHOWING_MS = 250

    def __init__(self, cfg: Config, preview: bool = False):
        _dpi_aware()
        self.cfg = cfg
        self.preview = preview
        self.windows: list[GardenWindow] = []
        self.monitor = None
        self.last_idle = 0
        self.hidden_at = 0.0
        self.root = tk.Tk()
        self.root.withdraw()
        self.frame_ms = max(10, int(1000 / cfg.fps))
        if not preview:
            from .idle import IdleMonitor

            self.monitor = IdleMonitor()

    def show(self):
        if self.windows:
            return
        _theme, palette, background = theme_colors(self.cfg)  # follows the system theme
        for rect in monitors():
            self.windows.append(GardenWindow(self.root, self.cfg, rect, self.hide, palette, background))
        if self.cfg.keep_screen_on:
            kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED)
        if self.monitor:
            self.last_idle = self.monitor.idle_ms() or 0
            self.root.after(self.POLL_SHOWING_MS, self._poll_showing)
        self.root.after(self.frame_ms, self._tick)

    def hide(self):
        if not self.windows:
            return
        for win in self.windows:
            win.close()
        self.windows = []
        self.hidden_at = time.monotonic()
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        if self.preview:
            self.root.destroy()

    def _tick(self):
        if not self.windows:
            return
        for win in self.windows:
            win.tick()
        self.root.after(self.frame_ms, self._tick)

    def _poll_idle(self):
        idle = self.monitor.idle_ms()
        if idle is not None and not self.windows:
            if idle >= self.cfg.timeout * 1000 and time.monotonic() - self.hidden_at > 2:
                if not (self.cfg.respect_inhibit and self.monitor.is_inhibited()):
                    self.show()
        self.root.after(self.POLL_IDLE_MS, self._poll_idle)

    def _poll_showing(self):
        """Idle time going *down* means the user touched something."""
        if not self.windows:
            return
        idle = self.monitor.idle_ms()
        if idle is not None:
            if idle + 50 < self.last_idle:
                self.hide()
                return
            self.last_idle = idle
        self.root.after(self.POLL_SHOWING_MS, self._poll_showing)

    def run(self):
        if self.preview:
            self.root.after(50, self.show)
        else:
            self.root.after(self.POLL_IDLE_MS, self._poll_idle)
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            kernel32.SetThreadExecutionState(ES_CONTINUOUS)
