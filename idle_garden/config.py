"""Settings: defaults < config.ini < command line.

Linux:   ~/.config/idle-garden/config.ini
Windows: %APPDATA%\\idle-garden\\config.ini
"""

from __future__ import annotations

import configparser
import os
import re
import sys
from dataclasses import dataclass, fields
from pathlib import Path

if sys.platform == "win32":
    CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "idle-garden"
else:
    CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "idle-garden"
CONFIG_FILE = CONFIG_DIR / "config.ini"

DEFAULT_INI = """\
# Idle Garden settings. Apply changes with:
#   idle-garden --restart

[garden]
# Seconds without mouse/keyboard input before the plant appears
timeout = 120

# Minutes for the plant to grow from a sprout until it fills the whole screen.
# After that it keeps living: old leaves are slowly replaced by new ones.
grow_minutes = 40

# Font used for the ASCII art ("auto" = Monospace on Linux, Consolas on Windows)
font = auto
font_size = 18

# Colour theme: auto (follow the system light/dark setting), dark or light
theme = auto

# Background colour for each theme
dark_background = #000000
light_background = #f4f1e8

# Do not start while a video player or a call asks the system to stay awake
respect_inhibit = true

# Keep the monitor on while the plant is showing
# (otherwise the system may still blank the screen after its own timeout)
keep_screen_on = false
"""


@dataclass
class Config:
    timeout: float = 120
    grow_minutes: float = 40
    font: str = "auto"
    font_size: float = 18
    theme: str = "auto"
    dark_background: str = "#000000"
    light_background: str = "#f4f1e8"
    respect_inhibit: bool = True
    keep_screen_on: bool = False
    fps: int = 15

    @property
    def font_family(self) -> str:
        if self.font and self.font.strip().lower() != "auto":
            return self.font
        return "Consolas" if sys.platform == "win32" else "Monospace"


def write_default_config() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(DEFAULT_INI, encoding="utf-8")
    return CONFIG_FILE


def load_config(path: Path = CONFIG_FILE) -> Config:
    cfg = Config()
    if not path.exists():
        return cfg
    # "#" starts a comment only after a space, so colours like #000000 survive
    parser = configparser.ConfigParser(inline_comment_prefixes=(";",))
    try:
        parser.read(path, encoding="utf-8")
    except configparser.Error as exc:
        print(f"idle-garden: ignoring broken config {path}: {exc}")
        return cfg
    if not parser.has_section("garden"):
        return cfg
    sec = parser["garden"]
    for key in list(sec):
        sec[key] = re.sub(r"\s+#.*$", "", sec[key]).strip()
    # 0.3 had a single "background", meant for the (then only) dark look
    if "background" in sec and "dark_background" not in sec:
        cfg.dark_background = sec.get("background").strip()
    for f in fields(Config):
        if f.name not in sec:
            continue
        try:
            if f.type in ("bool", bool):
                value = sec.getboolean(f.name)
            elif f.type in ("float", float):
                value = sec.getfloat(f.name)
            elif f.type in ("int", int):
                value = sec.getint(f.name)
            else:
                value = sec.get(f.name).strip()
        except ValueError:
            print(f"idle-garden: bad value for '{f.name}' in {path}, using default")
            continue
        setattr(cfg, f.name, value)
    return cfg
