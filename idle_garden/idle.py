"""How long has the user been idle?

Backends, tried in order:

0. Windows: ``GetLastInputInfo`` from user32 (only backend on Windows).
1. GNOME / Mutter ``org.gnome.Mutter.IdleMonitor`` over D-Bus. This is what
   Ubuntu uses by default and it works on both Wayland and X11.
2. The X11 ``XScreenSaver`` extension through ctypes (any X11 desktop:
   Xfce, MATE, Cinnamon, KDE on X11, ...).
3. The ``xprintidle`` command, if it is installed.

Every backend returns idle time in milliseconds, or ``None`` if it fails.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import shutil
import subprocess
import sys


class _MutterBackend:
    name = "gnome-mutter"

    def __init__(self):
        from gi.repository import Gio  # noqa: WPS433

        self._Gio = Gio
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.idle()  # raises if the service is not there

    def idle(self) -> int | None:
        res = self.bus.call_sync(
            "org.gnome.Mutter.IdleMonitor",
            "/org/gnome/Mutter/IdleMonitor/Core",
            "org.gnome.Mutter.IdleMonitor",
            "GetIdletime",
            None,
            None,
            self._Gio.DBusCallFlags.NONE,
            500,
            None,
        )
        return int(res.unpack()[0])


class _XssInfo(ctypes.Structure):
    _fields_ = [
        ("window", ctypes.c_ulong),
        ("state", ctypes.c_int),
        ("kind", ctypes.c_int),
        ("til_or_since", ctypes.c_ulong),
        ("idle", ctypes.c_ulong),
        ("eventMask", ctypes.c_ulong),
    ]


class _X11Backend:
    name = "x11-xss"

    def __init__(self):
        if not os.environ.get("DISPLAY"):
            raise RuntimeError("no X display")
        xlib = ctypes.cdll.LoadLibrary(ctypes.util.find_library("X11") or "libX11.so.6")
        xss = ctypes.cdll.LoadLibrary(ctypes.util.find_library("Xss") or "libXss.so.1")
        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        xlib.XDefaultRootWindow.restype = ctypes.c_ulong
        xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(_XssInfo)
        xss.XScreenSaverQueryInfo.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_XssInfo)]
        self.dpy = xlib.XOpenDisplay(None)
        if not self.dpy:
            raise RuntimeError("cannot open X display")
        self.root = xlib.XDefaultRootWindow(self.dpy)
        self.info = xss.XScreenSaverAllocInfo()
        self.xss = xss
        if self.idle() is None:
            raise RuntimeError("XScreenSaver extension not available")

    def idle(self) -> int | None:
        if not self.xss.XScreenSaverQueryInfo(self.dpy, self.root, self.info):
            return None
        return int(self.info.contents.idle)


class _XprintidleBackend:
    name = "xprintidle"

    def __init__(self):
        self.cmd = shutil.which("xprintidle")
        if not self.cmd or self.idle() is None:
            raise RuntimeError("xprintidle not available")

    def idle(self) -> int | None:
        try:
            out = subprocess.run([self.cmd], capture_output=True, text=True, timeout=1)
            return int(out.stdout.strip())
        except Exception:  # noqa: BLE001
            return None


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint32)]


class _WindowsBackend:
    name = "windows-getlastinputinfo"

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("not Windows")
        self.user32 = ctypes.windll.user32
        self.kernel32 = ctypes.windll.kernel32
        self.kernel32.GetTickCount.restype = ctypes.c_uint32
        self.info = _LastInputInfo()
        self.info.cbSize = ctypes.sizeof(_LastInputInfo)
        if self.idle() is None:
            raise RuntimeError("GetLastInputInfo failed")

    def idle(self) -> int | None:
        if not self.user32.GetLastInputInfo(ctypes.byref(self.info)):
            return None
        # both are 32-bit millisecond counters that wrap after ~49 days
        return (self.kernel32.GetTickCount() - self.info.dwTime) & 0xFFFFFFFF


def _windows_display_required() -> bool:
    """True if some app (a video player, a call) asked Windows to keep the display on."""
    ES_DISPLAY_REQUIRED = 0x00000002
    SYSTEM_EXECUTION_STATE = 16
    state = ctypes.c_ulong(0)
    fn = ctypes.windll.powrprof.CallNtPowerInformation
    fn.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong]
    fn.restype = ctypes.c_long
    status = fn(
        SYSTEM_EXECUTION_STATE, None, 0, ctypes.byref(state), ctypes.sizeof(state))
    return status == 0 and bool(state.value & ES_DISPLAY_REQUIRED)


class IdleMonitor:
    """Picks the first backend that works on this desktop."""

    def __init__(self):
        errors = []
        self.backend = None
        chain = (_WindowsBackend,) if sys.platform == "win32" else (
            _MutterBackend, _X11Backend, _XprintidleBackend)
        for cls in chain:
            try:
                self.backend = cls()
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{cls.name}: {exc}")
        if self.backend is None:
            raise RuntimeError(
                "Could not find a way to measure idle time.\n  "
                + "\n  ".join(errors)
                + "\nOn non-GNOME Wayland desktops this is not supported yet."
            )
        self._session_bus = None

    @property
    def name(self) -> str:
        return self.backend.name

    def idle_ms(self) -> int | None:
        try:
            return self.backend.idle()
        except Exception:  # noqa: BLE001
            return None

    def is_inhibited(self) -> bool:
        """True if some app (a video player, a meeting...) asked to stay awake."""
        if sys.platform == "win32":
            try:
                return _windows_display_required()
            except Exception:  # noqa: BLE001
                return False
        try:
            from gi.repository import Gio, GLib

            if self._session_bus is None:
                self._session_bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            res = self._session_bus.call_sync(
                "org.gnome.SessionManager",
                "/org/gnome/SessionManager",
                "org.gnome.SessionManager",
                "IsInhibited",
                GLib.Variant("(u)", (8,)),  # 8 = inhibit idle
                None,
                Gio.DBusCallFlags.NONE,
                500,
                None,
            )
            return bool(res.unpack()[0])
        except Exception:  # noqa: BLE001
            return False
