"""Dark and light colour themes, and detecting which one the OS uses.

``theme = auto`` (the default) follows the system: Ubuntu's *Settings →
Appearance → Style* (Light / Dark) or Windows' *Settings → Personalization →
Colors → Choose your app mode*. The theme is checked every time the tree
appears, so switching the system theme needs no restart.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from .plants import PALETTE

# The original night-time palette: bright young leaves that darken with age.
DARK: dict[str, tuple[int, int, int]] = dict(PALETTE)

# Daylight: ink on paper. Same colour names, so every frontend can swap them.
# Young leaves are a fresh yellow-green, old ones a deep green; everything is
# dark enough to stay readable on a light background.
LIGHT: dict[str, tuple[int, int, int]] = {
    "leaf_new": (112, 160, 24),
    "leaf_young": (96, 160, 40),
    "leaf_light": (70, 142, 50),
    "leaf": (46, 122, 52),
    "leaf_dark": (32, 100, 48),
    "leaf_deep": (22, 80, 42),
    "stem_new": (112, 154, 52),
    "stem_light": (92, 134, 52),
    "stem": (74, 112, 46),
    "stem_dark": (102, 78, 42),
    "wood": (122, 84, 48),
    "wood_dark": (90, 58, 34),
    "vine": (88, 136, 52),
    "vine_dark": (62, 106, 44),
    "ivy": (30, 110, 74),
    "ivy_light": (58, 144, 86),
    "soil_light": (150, 104, 62),
    "soil": (118, 80, 48),
    "soil_dark": (88, 60, 38),
    "pebble": (128, 124, 116),
}

THEMES = {"dark": DARK, "light": LIGHT}
DEFAULT_BACKGROUND = {"dark": "#000000", "light": "#f4f1e8"}


# --------------------------------------------------------------- detection

def _run(cmd: list[str]) -> str | None:
    if not shutil.which(cmd[0]):
        return None
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=1)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _linux_portal() -> str | None:
    """org.freedesktop.appearance color-scheme: 1 = dark, 2 = light, 0 = no preference."""
    try:
        from gi.repository import Gio, GLib

        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        res = bus.call_sync(
            "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Settings", "Read",
            GLib.Variant("(ss)", ("org.freedesktop.appearance", "color-scheme")),
            None, Gio.DBusCallFlags.NONE, 500, None)
        value = res.unpack()[0]
        while isinstance(value, (tuple, list)) or hasattr(value, "unpack"):  # nested variants
            value = value.unpack() if hasattr(value, "unpack") else value[0]
        return {1: "dark", 2: "light"}.get(int(value))
    except Exception:  # noqa: BLE001
        return None


def _linux_gsettings() -> str | None:
    """GNOME / Ubuntu: color-scheme (22.04+), then the GTK theme name (20.04)."""
    scheme = _run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"])
    if scheme:
        if "dark" in scheme:
            return "dark"
        if "light" in scheme:
            return "light"
    gtk = _run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"])
    if gtk:
        return "dark" if "dark" in gtk.lower() else "light"
    return None


def _linux_env() -> str | None:
    gtk = os.environ.get("GTK_THEME", "")
    if gtk:
        return "dark" if "dark" in gtk.lower() else "light"
    return None


def _windows() -> str | None:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return "light" if value else "dark"
    except OSError:
        return None


def detect_system_theme() -> str | None:
    """'dark', 'light' or None if the system does not say."""
    if sys.platform == "win32":
        return _windows()
    if sys.platform == "darwin":
        out = _run(["defaults", "read", "-g", "AppleInterfaceStyle"])
        return "dark" if out and "dark" in out.lower() else "light"
    for probe in (_linux_env, _linux_portal, _linux_gsettings):
        result = probe()
        if result:
            return result
    return None


# ----------------------------------------------------------------- resolve

def hex_to_rgb(value: str, fallback: tuple[int, int, int] = (0, 0, 0)) -> tuple[int, int, int]:
    h = value.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return fallback


def resolve_theme(name: str) -> str:
    """Turn 'auto' / 'dark' / 'light' into 'dark' or 'light'."""
    name = (name or "auto").strip().lower()
    if name in THEMES:
        return name
    return detect_system_theme() or "dark"


def theme_colors(cfg) -> tuple[str, dict[str, tuple[int, int, int]], tuple[int, int, int]]:
    """(theme name, palette, background rgb 0..255) for a :class:`Config`."""
    name = resolve_theme(cfg.theme)
    bg = cfg.dark_background if name == "dark" else cfg.light_background
    if not bg or bg.strip().lower() == "auto":
        bg = DEFAULT_BACKGROUND[name]
    return name, THEMES[name], hex_to_rgb(bg, hex_to_rgb(DEFAULT_BACKGROUND[name]))
