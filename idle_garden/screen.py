"""Fullscreen GTK windows that show the garden, and the idle-watching daemon."""

from __future__ import annotations

import signal
import sys
import time

import os

import cairo
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gio, GLib  # noqa: E402

# On GNOME Wayland a window opened by a background program is not allowed to
# steal focus and may end up *behind* the active window. Through XWayland we
# can mark it "always on top", so prefer X11 unless the user says otherwise.
Gdk.set_allowed_backends(os.environ.get("IDLE_GARDEN_GDK_BACKEND", "x11,*"))

from gi.repository import Gtk  # noqa: E402

from .config import Config  # noqa: E402
from .nature import LivingGarden, garden_options  # noqa: E402
from .themes import theme_colors  # noqa: E402

# Mouse jitter smaller than this (in pixels) does not wake the screen.
MOTION_THRESHOLD = 10
# Ignore pointer events for a moment after the window appears.
GRACE_SECONDS = 0.8


class GardenWindow(Gtk.Window):
    def __init__(self, cfg: Config, monitor: int | None, on_activity, palette, background):
        super().__init__(title="Idle Garden")
        self.cfg = cfg
        self.palette = palette
        self.background = tuple(c / 255 for c in background)
        self.on_activity = on_activity
        self.garden: LivingGarden | None = None
        self.metrics = None  # (cell_w, cell_h, ascent)
        self.shown_at = time.monotonic()
        self.last_tick = self.shown_at
        self.last_version = -1
        self.pointer_origin = None

        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_app_paintable(True)

        area = Gtk.DrawingArea()
        area.connect("draw", self._on_draw)
        self.add(area)
        self.area = area

        self.add_events(
            Gdk.EventMask.KEY_PRESS_MASK
            | Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.SCROLL_MASK
            | Gdk.EventMask.TOUCH_MASK
        )
        self.connect("key-press-event", self._wake)
        self.connect("button-press-event", self._wake)
        self.connect("scroll-event", self._wake)
        self.connect("touch-event", self._wake)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("realize", self._on_realize)
        self.connect("delete-event", lambda *_: True)  # only input closes us

        if monitor is not None:
            self.fullscreen_on_monitor(self.get_screen(), monitor)
        else:
            self.fullscreen()
        self.tick_id = GLib.timeout_add(max(10, int(1000 / cfg.fps)), self._tick)

    # -- input ------------------------------------------------------------- #

    def _on_realize(self, *_):
        win = self.get_window()
        if win is not None:
            win.set_cursor(Gdk.Cursor.new_from_name(win.get_display(), "none"))

    def _wake(self, *_):
        if time.monotonic() - self.shown_at > 0.15:
            self.on_activity()
        return True

    def _on_motion(self, _w, event):
        if time.monotonic() - self.shown_at < GRACE_SECONDS:
            self.pointer_origin = (event.x_root, event.y_root)
            return True
        if self.pointer_origin is None:
            self.pointer_origin = (event.x_root, event.y_root)
            return True
        ox, oy = self.pointer_origin
        if abs(event.x_root - ox) + abs(event.y_root - oy) > MOTION_THRESHOLD:
            self.on_activity()
        return True

    # -- animation --------------------------------------------------------- #

    def _tick(self):
        now = time.monotonic()
        dt, self.last_tick = now - self.last_tick, now
        if self.garden is not None:
            self.garden.update(min(dt, 0.5))
            if self.garden.version != self.last_version:
                self.area.queue_draw()
        return True

    def _on_draw(self, widget, cr):
        w, h = widget.get_allocated_width(), widget.get_allocated_height()
        cr.set_source_rgb(*self.background)
        cr.paint()

        cr.select_font_face(self.cfg.font_family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(self.cfg.font_size)
        if self.metrics is None:
            ascent, _descent, height, *_ = cr.font_extents()
            cell_w = cr.text_extents("M")[4] or self.cfg.font_size * 0.6
            self.metrics = (cell_w, height, ascent)
        cell_w, cell_h, ascent = self.metrics
        cols, rows = max(20, int(w // cell_w)), max(12, int(h // cell_h))

        if self.garden is None:
            self.garden = LivingGarden(cols, rows, self.cfg.grow_minutes, **garden_options(self.cfg))
        else:
            self.garden.resize(cols, rows)
        self.last_version = self.garden.version

        gcols, grows = self.garden.grid_cols, self.garden.grid_rows
        ox = (w - gcols * cell_w) / 2
        oy = (h - grows * cell_h) / 2 + ascent
        # One string per (colour, row) with spaces elsewhere: far fewer Cairo
        # calls than drawing each character on its own.
        rows_by_color: dict[str, dict[int, list[str]]] = {}
        for (x, y), (ch, color) in self.garden.cells.items():
            line = rows_by_color.setdefault(color, {}).get(y)
            if line is None:
                line = rows_by_color[color][y] = [" "] * gcols
            line[x] = ch
        for color, lines in rows_by_color.items():
            r, g, b = self.palette.get(color, (128, 128, 128))
            cr.set_source_rgb(r / 255, g / 255, b / 255)
            for y, chars in lines.items():
                cr.move_to(ox, oy + y * cell_h)
                cr.show_text("".join(chars).rstrip())
        return True

    def close_garden(self):
        if self.tick_id:
            GLib.source_remove(self.tick_id)
            self.tick_id = 0
        self.destroy()


class Daemon:
    """Watches idle time and shows/hides the garden on every monitor."""

    POLL_IDLE_MS = 1000
    POLL_SHOWING_MS = 250

    def __init__(self, cfg: Config, preview: bool = False):
        self.cfg = cfg
        self.preview = preview
        self.windows: list[GardenWindow] = []
        self.monitor = None
        self.last_idle = 0
        self.inhibit_cookie = None
        self.hidden_at = 0.0
        if not preview:
            from .idle import IdleMonitor

            self.monitor = IdleMonitor()
            print(f"idle-garden: watching idle time via {self.monitor.name}, "
                  f"garden after {cfg.timeout:g}s", flush=True)

    # -- show / hide ------------------------------------------------------- #

    def show(self):
        if self.windows:
            return
        display = Gdk.Display.get_default()
        n = display.get_n_monitors() if display else 1
        # checked every time, so switching the system theme needs no restart
        _theme, palette, background = theme_colors(self.cfg)
        for i in range(max(1, n)):
            win = GardenWindow(self.cfg, i if n > 1 else None, self.hide, palette, background)
            win.show_all()
            win.present()
            self.windows.append(win)
        if self.cfg.keep_screen_on:
            self._inhibit(True)
        if self.monitor:
            self.last_idle = self.monitor.idle_ms() or 0
            GLib.timeout_add(self.POLL_SHOWING_MS, self._poll_showing)

    def hide(self):
        if not self.windows:
            return
        for win in self.windows:
            win.close_garden()
        self.windows = []
        self.hidden_at = time.monotonic()
        self._inhibit(False)
        if self.preview:
            Gtk.main_quit()

    # -- polling ----------------------------------------------------------- #

    def _poll_idle(self):
        idle = self.monitor.idle_ms()
        if idle is None or self.windows:
            return True
        if idle >= self.cfg.timeout * 1000 and time.monotonic() - self.hidden_at > 2:
            if not (self.cfg.respect_inhibit and self.monitor.is_inhibited()):
                self.show()
        return True

    def _poll_showing(self):
        """Idle time going *down* means the user touched something."""
        if not self.windows:
            return False
        idle = self.monitor.idle_ms()
        if idle is not None:
            if idle + 50 < self.last_idle:
                self.hide()
                return False
            self.last_idle = idle
        return True

    # -- keep the screen on ------------------------------------------------ #

    def _inhibit(self, on: bool):
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            if on and self.inhibit_cookie is None:
                res = bus.call_sync(
                    "org.gnome.SessionManager", "/org/gnome/SessionManager",
                    "org.gnome.SessionManager", "Inhibit",
                    GLib.Variant("(susu)", ("idle-garden", 0, "Growing a garden", 8)),
                    None, Gio.DBusCallFlags.NONE, 1000, None)
                self.inhibit_cookie = res.unpack()[0]
            elif not on and self.inhibit_cookie is not None:
                bus.call_sync(
                    "org.gnome.SessionManager", "/org/gnome/SessionManager",
                    "org.gnome.SessionManager", "Uninhibit",
                    GLib.Variant("(u)", (self.inhibit_cookie,)),
                    None, Gio.DBusCallFlags.NONE, 1000, None)
                self.inhibit_cookie = None
        except Exception as exc:  # noqa: BLE001
            print(f"idle-garden: cannot change screen inhibit: {exc}", file=sys.stderr)

    # -- main loop --------------------------------------------------------- #

    def run(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda *_: Gtk.main_quit() or False)
        if self.preview:
            GLib.idle_add(lambda: self.show() and False)
        else:
            GLib.timeout_add(self.POLL_IDLE_MS, self._poll_idle)
        try:
            Gtk.main()
        except KeyboardInterrupt:
            pass
        finally:
            self._inhibit(False)
