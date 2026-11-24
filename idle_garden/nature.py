"""Seasons, wind and visitors: the life *around* the tree.

:class:`LivingGarden` wraps the plain :class:`~idle_garden.plants.Garden`:

* **Seasons** follow today's date and your half of the world: fresh greens in
  spring, deep greens in summer, yellow, orange and red leaves that fall and
  pile up on the ground in autumn, a half-bare tree with snow on its leaves and
  snow falling in winter. Early autumn is still mostly green, late autumn
  mostly bare.
* **Wind** comes in gusts that roll across the screen and ruffle the leaves.
* **Birds** fly in, sit on a branch (or hop on the ground) for a while and fly
  off; **butterflies** flutter about on spring and summer days.

The tree itself is not touched: the season is a filter over its cells, and the
weather and animals are drawn on top. Pure Python, like ``plants.py``.
"""

from __future__ import annotations

import datetime as _dt
import math
import os
import random
import sys
from pathlib import Path

from .plants import ASPECT, Garden

SEASONS = ("spring", "summer", "autumn", "winter")

# Extra colours for the dark theme (the light ones live in themes.py).
COLORS: dict[str, tuple[int, int, int]] = {
    "aut_gold": (238, 200, 76),
    "aut_yellow": (214, 172, 54),
    "aut_orange": (226, 132, 48),
    "aut_red": (200, 74, 48),
    "aut_rust": (160, 86, 48),
    "aut_brown": (124, 88, 56),
    "win_leaf": (64, 100, 82),
    "snow": (236, 242, 250),
    "snow_dim": (168, 182, 202),
    "wind": (182, 218, 156),
    "bird": (158, 122, 90),
    "bird_dark": (124, 116, 112),
    "bird_red": (220, 78, 64),
    "bird_blue": (100, 154, 218),
    "fly_yellow": (246, 216, 84),
    "fly_white": (236, 236, 228),
    "fly_orange": (242, 148, 62),
    "fly_blue": (126, 176, 250),
}

AUTUMN = ("aut_gold", "aut_yellow", "aut_orange", "aut_red", "aut_rust", "aut_brown")
SPRING = {"leaf_deep": "leaf_dark", "leaf_dark": "leaf", "leaf": "leaf_light"}
LEAFY = ("leaf", "ivy", "aut_", "win_", "snow")
TUMBLE = "&%~'`,"  # a falling leaf turning over

FLY_FRAMES = ("\\v/", "-v-", "/v\\", "-v-")


# ---------------------------------------------------------------- seasons

# Time zones of the southern half of the world (IANA prefixes, Windows names).
_SOUTH_TZ = (
    "Australia/", "Antarctica/", "Pacific/Auckland", "Pacific/Chatham", "NZ", "Pacific/Fiji",
    "Pacific/Noumea", "Pacific/Tongatapu", "Pacific/Tahiti", "Pacific/Efate", "Pacific/Apia",
    "America/Argentina", "America/Buenos_Aires", "America/Santiago", "America/Punta_Arenas",
    "America/Sao_Paulo", "America/Montevideo", "America/Asuncion", "America/La_Paz", "America/Lima",
    "America/Cuiaba", "America/Campo_Grande", "America/Bahia", "America/Recife", "America/Maceio",
    "Chile/", "Brazil/", "Africa/Johannesburg", "Africa/Maputo", "Africa/Harare", "Africa/Windhoek",
    "Africa/Gaborone", "Africa/Lusaka", "Africa/Maseru", "Africa/Mbabane", "Africa/Lubumbashi",
    "Africa/Blantyre", "Africa/Dar_es_Salaam", "Africa/Luanda", "Indian/Antananarivo",
    "Indian/Mauritius", "Indian/Reunion", "Indian/Comoro", "Indian/Mayotte",
)
_SOUTH_WIN = (
    "AUS ", "Australia", "Tasmania", "New Zealand", "Chatham", "Fiji", "Tonga", "Samoa",
    "South Africa", "Namibia", "Mauritius", "Argentina", "E. South America", "Pacific SA",
    "Paraguay", "Montevideo", "Magallanes", "Bahia", "Central Brazilian",
)

_SEASON_OF_MONTH = {12: 3, 1: 3, 2: 3, 3: 0, 4: 0, 5: 0, 6: 1, 7: 1, 8: 1, 9: 2, 10: 2, 11: 2}


def _timezone_name() -> str:
    tz = os.environ.get("TZ", "").lstrip(":")
    if tz:
        return tz
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation") as key:
                return str(winreg.QueryValueEx(key, "TimeZoneKeyName")[0])
        except OSError:
            return ""
    try:
        name = Path("/etc/timezone").read_text(encoding="utf-8").strip()  # Debian / Ubuntu
        if name:
            return name
    except OSError:
        pass
    target = os.path.realpath("/etc/localtime")
    return target.split("zoneinfo/", 1)[1] if "zoneinfo/" in target else ""


def detect_hemisphere(tz: str | None = None) -> str:
    """'north' or 'south', guessed from the time zone (north if unsure)."""
    tz = _timezone_name() if tz is None else tz
    if tz.startswith(_SOUTH_TZ) or any(name in tz for name in _SOUTH_WIN):
        return "south"
    return "north"


def season_on(day: _dt.date, hemisphere: str = "north") -> tuple[str, float]:
    """(season, how far into it 0..1) for a date, by meteorological seasons
    (winter = December to February in the north)."""
    north = _SEASON_OF_MONTH[day.month]
    first_month = (3, 6, 9, 12)[north]
    year = day.year - 1 if first_month == 12 and day.month < 12 else day.year
    progress = (day - _dt.date(year, first_month, 1)).days / 91.0
    idx = (north + 2) % 4 if hemisphere == "south" else north
    return SEASONS[idx], min(1.0, max(0.0, progress))


def resolve_season(setting: str = "auto", hemisphere: str = "auto",
                   now: _dt.datetime | None = None) -> tuple[str, float]:
    """Turn the settings into (season, progress 0..1)."""
    now = now or _dt.datetime.now()
    hem = (hemisphere or "auto").strip().lower()
    if hem not in ("north", "south"):
        hem = detect_hemisphere()
    season, progress = season_on(now.date(), hem)
    wanted = (setting or "auto").strip().lower()
    wanted = "autumn" if wanted == "fall" else wanted
    if wanted in SEASONS and wanted != season:
        return wanted, 0.5
    return season, progress


def garden_options(cfg) -> dict:
    """LivingGarden keyword arguments from a :class:`~idle_garden.config.Config`."""
    return {"season": cfg.season, "hemisphere": cfg.hemisphere, "animals": cfg.animals, "wind": cfg.wind}


# ------------------------------------------------------------------ noise

def _hash(x: int, y: int, salt: int = 0) -> float:
    """A repeatable random number 0..1 for a cell."""
    h = (x * 374761393 + y * 668265263 + salt * 2246822519) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


class _Noise:
    """Smooth random patches about ``size`` rows across, values 0..1."""

    def __init__(self, rng: random.Random, size: float):
        self.waves = []
        for _ in range(4):
            a = rng.uniform(0, math.pi)
            f = 2 * math.pi / (size * rng.uniform(0.7, 1.4))
            self.waves.append((math.cos(a) * f * ASPECT, math.sin(a) * f, rng.uniform(0, 6.3)))

    def __call__(self, x: int, y: int) -> float:
        s = sum(math.sin(x * fx + y * fy + ph) for fx, fy, ph in self.waves) / len(self.waves)
        return min(1.0, max(0.0, 0.5 + 0.8 * s))


class SeasonLook:
    """How the leaves look in a season: colour, and whether they have fallen."""

    def __init__(self, season: str, progress: float, rng: random.Random):
        self.season, self.p = season, progress
        self.salt = rng.randrange(1 << 16)
        self._bare_n, self._turn_n, self._hue_n = _Noise(rng, 7), _Noise(rng, 10), _Noise(rng, 6)
        self._vals: dict[tuple[int, int], tuple[float, float, float, float]] = {}
        self.turned = 0.4 + 0.55 * progress  # autumn: share of yellow / red leaves
        self.bare = 0.04 + 0.32 * progress  # autumn: share already fallen

    def _cell(self, x: int, y: int):
        v = self._vals.get((x, y))
        if v is None:
            h = _hash(x, y, self.salt)
            v = self._vals[(x, y)] = (0.75 * self._bare_n(x, y) + 0.25 * _hash(x, y, self.salt + 1),
                                      0.8 * self._turn_n(x, y) + 0.2 * _hash(x, y, self.salt + 2),
                                      self._hue_n(x, y), h)
        return v

    def leaf(self, x: int, y: int, ch: str, color: str) -> tuple[str, str] | None:
        """The leaf cell as it looks this season, or None if it has fallen."""
        season = self.season
        if season == "summer":
            return ch, color
        ivy = color.startswith("ivy")
        bare, turn, hue, h = self._cell(x, y)
        if season == "spring":
            return (ch, color) if ivy or h > 0.7 else (ch, SPRING.get(color, color))
        if season == "autumn":
            if bare < self.bare * (0.5 if ivy else 1.0):
                return None
            if turn < self.turned * (1.2 if ivy else 1.0):
                k = hue * 0.7 + self.p * 0.45 + (h - 0.5) * 0.3 - 0.12 + (0.3 if ivy else 0.0)
                return ch, AUTUMN[int(min(0.999, max(0.0, k)) * len(AUTUMN))]
            return ch, ("leaf_light" if color in ("leaf_new", "leaf_young") else color)
        # winter: ivy stays green, most leaves are gone, the rest are dark
        if bare < (0.25 if ivy else 0.6):
            return None
        if ivy:
            return ch, "ivy"
        return ch, ("leaf_deep" if h < 0.4 else "win_leaf")


# ------------------------------------------------------------------- wind

class Wind:
    """A steady breeze plus gusts that roll across the screen."""

    GAPS = {"spring": (5, 16), "summer": (8, 24), "autumn": (3, 10), "winter": (4, 13)}
    BREEZE = {"spring": 0.4, "summer": 0.25, "autumn": 0.8, "winter": 0.6}

    def __init__(self, rng: random.Random, cols: int, season: str, enabled: bool = True):
        self.rng, self.cols, self.season, self.enabled = rng, cols, season, enabled
        self.dir = rng.choice((-1, 1))
        self.gusts: list[list[float]] = []  # [front x, speed, half width, strength]
        self.wait = rng.uniform(2, 7)
        self.t = 0.0

    @property
    def breeze(self) -> float:
        return self.BREEZE[self.season] * self.dir if self.enabled else 0.0

    def update(self, dt: float) -> bool:
        self.t += dt
        if not self.enabled:
            return False
        rng = self.rng
        self.wait -= dt
        if self.wait <= 0:
            self.wait = rng.uniform(*self.GAPS[self.season])
            if rng.random() < 0.12:
                self.dir = -self.dir
            width = rng.uniform(6, 16)
            self.gusts.append([-width if self.dir > 0 else self.cols + width,
                               self.dir * rng.uniform(16, 30), width, rng.uniform(0.5, 1.0)])
        for g in self.gusts:
            g[0] += g[1] * dt
        self.gusts = [g for g in self.gusts if -2 * g[2] <= g[0] <= self.cols + 2 * g[2]]
        return bool(self.gusts)

    def at(self, x: float) -> float:
        """Signed gust strength at column x, about -1..1."""
        s = 0.0
        for gx, v, w, strength in self.gusts:
            d = (x - gx) / w
            if -1 < d < 1:
                s += strength * (1 - d * d) * (1 if v > 0 else -1)
        return s

    def drift(self, x: float) -> float:
        """How fast falling things are blown sideways, columns per second."""
        return self.breeze + self.at(x) * 6


# ---------------------------------------------------------------- weather

class Weather:
    """Falling leaves in autumn, snow in winter, and what piles up on the ground."""

    def __init__(self, rng: random.Random, cols: int, rows: int, season: str, progress: float, wind: Wind):
        self.rng, self.cols, self.rows = rng, cols, rows
        self.season, self.p, self.wind = season, progress, wind
        self.parts: list[list] = []  # [x, y, fall speed, phase, colour, char index]
        self.litter: dict[tuple[int, int], tuple[str, str]] = {}
        self._acc = 0.0
        self._snow_phase = rng.uniform(0, 6.3)
        self._seeded = False

    def _seed_ground(self, cells) -> None:
        """Start late autumn with some leaves on the ground, winter with snow."""
        rng, y = self.rng, self.rows - 1
        free = [x for x in range(self.cols) if (x, y) not in cells]
        if self.season == "autumn":
            for x in rng.sample(free, int(len(free) * (0.05 + 0.4 * self.p))):
                self.litter[(x, y)] = (rng.choice(",_&%"), rng.choice(AUTUMN[2:]))
        elif self.season == "winter":
            for x in free:
                if rng.random() < 0.8:
                    self.litter[(x, y)] = (rng.choice("__.") , "snow")

    def update(self, dt: float, cells, sources) -> bool:
        if not self._seeded:
            self._seeded = True
            self._seed_ground(cells)
        rng, cols, rows = self.rng, self.cols, self.rows
        if self.season == "autumn" and sources:
            gusty = any(abs(self.wind.at(x)) > 0.3 for x in range(0, cols, 8))
            rate = (0.25 + len(sources) / 1600) * (3.0 if gusty else 1.0)
            self._acc += dt * rate
            while self._acc >= 1:
                self._acc -= 1
                # in a gust, leaves are torn off where the wind is
                x, y = max((rng.choice(sources) for _ in range(4)), key=lambda p: abs(self.wind.at(p[0])))
                color = cells.get((x, y), ("", rng.choice(AUTUMN)))[1]
                if not color.startswith("aut_"):
                    color = rng.choice(AUTUMN)
                self.parts.append([x + 0.5, y + 0.5, rng.uniform(1.0, 2.2), rng.uniform(0, 6.3), color,
                                   rng.randrange(len(TUMBLE))])
        elif self.season == "winter":
            # snowfall comes and goes over a few minutes
            amount = max(0.0, 0.3 + 0.7 * math.sin(self.wind.t * 2 * math.pi / 300 + self._snow_phase))
            self._acc += dt * cols / 22 * amount
            while self._acc >= 1:
                self._acc -= 1
                x = rng.uniform(-10, cols + 10) - self.wind.breeze * 8
                self.parts.append([x, -0.5, rng.uniform(1.4, 3.0), rng.uniform(0, 6.3),
                                   "snow" if rng.random() < 0.7 else "snow_dim", rng.random() < 0.3])
        if not self.parts:
            return False

        alive = []
        cap = cols * (0.9 if self.season == "winter" else 0.6)
        for part in self.parts:
            x, y, vy, phase = part[0], part[1], part[2], part[3]
            leaf = self.season == "autumn"
            phase += dt * (3.0 if leaf else 1.5)
            sway = math.sin(phase) * (1.6 if leaf else 0.6)
            x += (self.wind.drift(x) * (1.0 if leaf else 0.7) + sway) * dt
            y += vy * dt * (0.8 + 0.4 * abs(math.cos(phase)) if leaf else 1.0)
            part[0], part[1], part[3] = x, y, phase
            if y >= rows - 1:  # landed
                pos = (int(x), rows - 1)
                if 0 <= pos[0] < cols and pos not in cells and len(self.litter) < cap:
                    self.litter[pos] = ((rng.choice(",_&%"), part[4]) if leaf
                                        else (rng.choice("__."), "snow"))
                continue
            if -12 <= x < cols + 12:
                alive.append(part)
        self.parts = alive
        return True

    def draw(self, out: dict) -> None:
        cols, rows = self.cols, self.rows
        for pos, cell in self.litter.items():
            if pos not in out:  # the plant grows over it
                out[pos] = cell
        for x, y, _vy, phase, color, k in self.parts:
            cx, cy = int(x), int(y)
            if 0 <= cx < cols and 0 <= cy < rows:
                if self.season == "autumn":
                    ch = TUMBLE[(k + int(phase * 1.3)) % len(TUMBLE)]
                else:
                    ch = "*" if k else "."
                out[(cx, cy)] = (ch, color)


# --------------------------------------------------------------- visitors

class Bird:
    def __init__(self, x, y, target, color, rng):
        self.x, self.y = x, y
        self.target = target  # (x, y, perch?) where it flies to
        self.color = color
        self.state = "in"
        self.t = rng.uniform(0, 1)
        self.timer = 0.0
        self.facing = 1
        self.peck = 0.0
        self.speed = rng.uniform(6, 9)  # rows per second

    def glyph(self, ground: bool) -> str:
        if self.state != "sit":
            return FLY_FRAMES[int(self.t * 9) % len(FLY_FRAMES)]
        if self.peck > 0:
            return "(o." if self.facing > 0 else ".o)"
        return "(o>" if self.facing > 0 else "<o)"


class Butterfly:
    def __init__(self, x, y, color, rng, life):
        self.x, self.y = x, y
        self.color = color
        self.ang = rng.uniform(0, 2 * math.pi)
        self.speed = rng.uniform(3, 6)  # columns per second
        self.t = rng.uniform(0, 1)
        self.life = life
        self.rest = 0.0


class Visitors:
    """Birds that drop by and butterflies that flutter about."""

    def __init__(self, rng: random.Random, cols: int, rows: int, season: str, enabled: bool = True,
                 clock=None):
        self.rng, self.cols, self.rows, self.season = rng, cols, rows, season
        self.enabled = enabled
        self.clock = clock or _dt.datetime.now
        self.birds: list[Bird] = []
        self.flies: list[Butterfly] = []
        self.next_bird = rng.uniform(8, 25)
        self.next_fly = rng.uniform(5, 18)
        self.butterfly_season = season in ("spring", "summer")

    def _hour(self) -> int:
        return self.clock().hour

    # -- birds ------------------------------------------------------------- #

    def _perches(self, cells):
        """Free spots right above branches, on top of the foliage, and on the ground."""
        cols, rows = self.cols, self.rows
        branches, tops, ground = [], [], []
        for (x, y), (ch, color) in cells.items():
            if y < 3 or y > rows - 2 or x < 2 or x > cols - 3:
                continue
            if (x - 1, y - 1) in cells or (x, y - 1) in cells or (x + 1, y - 1) in cells:
                continue
            if color.startswith(("wood", "stem")) and ch in "~/\\":
                branches.append((x, y - 1))
            elif color.startswith(LEAFY):
                tops.append((x, y - 1))
        y = rows - 1
        for x in range(3, cols - 3):
            if (x - 1, y) not in cells and (x, y) not in cells and (x + 1, y) not in cells:
                ground.append((x, y))
        taken = [(round(b.target[0]), round(b.target[1])) for b in self.birds]

        def free(spots):
            return [s for s in spots if all(abs(s[0] - tx) > 4 or s[1] != ty for tx, ty in taken)]

        branches, tops, ground = free(branches), free(tops), free(ground)
        roll = self.rng.random()
        for chance, spots in ((0.6, branches), (0.85, tops), (1.0, ground)):
            if roll < chance and spots:
                return self.rng.choice(spots)
        spots = branches or tops or ground
        return self.rng.choice(spots) if spots else None

    def _bird_color(self) -> str:
        rng = self.rng
        if self.season == "winter":
            return rng.choice(("bird_red", "bird_red", "bird_dark", "bird"))  # bullfinches
        return rng.choice(("bird", "bird", "bird_dark", "bird_blue"))

    def _spawn_bird(self, cells, grown: float) -> None:
        rng, cols, rows = self.rng, self.cols, self.rows
        side = rng.choice((-1, 1))
        sx, sy = (-3 if side < 0 else cols + 2), rng.uniform(0, rows * 0.35)
        perch = self._perches(cells) if grown > 0.12 and rng.random() < 0.85 else None
        if perch:
            target = (perch[0], perch[1], True)
        else:  # just passing by
            target = (cols + 4 if side < 0 else -5, rng.uniform(0, rows * 0.4), False)
        bird = Bird(sx, sy, target, self._bird_color(), rng)
        self.birds.append(bird)
        if not perch and rng.random() < 0.4:  # a pair flying together
            mate = Bird(sx - side * rng.uniform(3, 6), sy + rng.uniform(-2, 2),
                        (target[0], target[1] + rng.uniform(-2, 2), False), bird.color, rng)
            mate.speed = bird.speed
            self.birds.append(mate)

    def _move_bird(self, b: Bird, dt: float) -> bool:
        """Fly towards the target; True when there."""
        tx, ty = b.target[0], b.target[1]
        dx, dy = (tx - b.x) * ASPECT, ty - b.y
        dist = math.hypot(dx, dy)
        step = b.speed * dt
        if dist <= step:
            b.x, b.y = tx, ty
            return True
        b.x += dx / dist * step / ASPECT
        b.y += dy / dist * step
        if abs(dx) > 0.01:
            b.facing = 1 if dx > 0 else -1
        return False

    def _update_birds(self, dt: float) -> None:
        rng = self.rng
        keep = []
        for b in self.birds:
            b.t += dt
            if b.state == "in":
                if self._move_bird(b, dt):
                    if not b.target[2]:
                        continue  # flew off the screen
                    b.state, b.timer = "sit", rng.uniform(8, 35)
                    b.x, b.y = round(b.x), round(b.y)
            elif b.state == "sit":
                b.timer -= dt
                b.peck = max(0.0, b.peck - dt)
                if rng.random() < dt * 0.3:
                    b.facing = -b.facing
                if b.y >= self.rows - 1 and b.peck <= 0 and rng.random() < dt * 0.8:
                    b.peck = 0.35  # pecking at the ground
                if b.timer <= 0:
                    b.state = "out"
                    out_x = self.cols + 4 if rng.random() < 0.5 else -5
                    b.target = (out_x, rng.uniform(-3, self.rows * 0.3), False)
            elif self._move_bird(b, dt):
                continue
            keep.append(b)
        self.birds = keep

    # -- butterflies ------------------------------------------------------- #

    def _update_flies(self, dt: float, cells) -> None:
        rng, cols, rows = self.rng, self.cols, self.rows
        keep = []
        for f in self.flies:
            f.t += dt
            f.life -= dt
            if f.rest > 0:
                f.rest -= dt
                keep.append(f)
                continue
            if f.life > 0:
                f.ang += rng.gauss(0, 2.2) * math.sqrt(dt)
                # stay on the screen, away from the very top and bottom
                cx, cy = cols / 2 - f.x, rows * 0.5 - f.y
                if not (4 < f.x < cols - 5 and 3 < f.y < rows - 3):
                    want = math.atan2(cy, cx * ASPECT)
                    f.ang += math.sin(want - f.ang) * 3 * dt
            else:  # time to go: head for the nearest side
                want = 0.0 if f.x > cols / 2 else math.pi
                f.ang += math.sin(want - f.ang) * 3 * dt
            f.x += math.cos(f.ang) * f.speed * dt
            f.y += math.sin(f.ang) * f.speed * ASPECT * dt
            if f.life <= 0 and not (-3 <= f.x <= cols + 2):
                continue
            pos = (int(f.x), int(round(f.y)) + 1)
            if f.life > 3 and rng.random() < dt * 0.08 and cells.get(pos, ("", ""))[1].startswith(LEAFY):
                f.rest = rng.uniform(2, 7)  # settles on a leaf for a moment
            keep.append(f)
        self.flies = keep

    # -- main -------------------------------------------------------------- #

    def update(self, dt: float, cells, grown: float) -> bool:
        if not self.enabled:
            return False
        rng = self.rng
        self.next_bird -= dt
        if self.next_bird <= 0:
            hour = self._hour()
            night = hour < 6 or hour >= 21
            gap = (35, 100) if self.season == "winter" else (20, 70)
            self.next_bird = rng.uniform(*gap) * (4 if night else 1)
            if len(self.birds) < 3 and not (night and rng.random() < 0.75):
                self._spawn_bird(cells, grown)
        if self.butterfly_season:
            self.next_fly -= dt
            if self.next_fly <= 0:
                self.next_fly = rng.uniform(15, 45)
                hour = self._hour()
                limit = 3 if self.season == "summer" else 2
                if 8 <= hour < 20 and len(self.flies) < limit and grown > 0.05:
                    side = rng.choice((-1, 1))
                    f = Butterfly(-2 if side < 0 else self.cols + 1, rng.uniform(self.rows * 0.2, self.rows * 0.8),
                                  rng.choice(("fly_yellow", "fly_white", "fly_orange", "fly_blue")),
                                  rng, rng.uniform(25, 70))
                    f.ang = 0.0 if side < 0 else math.pi
                    self.flies.append(f)
        self._update_birds(dt)
        self._update_flies(dt, cells)
        return bool(self.birds or self.flies)

    def draw(self, out: dict) -> None:
        cols, rows = self.cols, self.rows

        def put(x, y, text, color):
            # a blank cell on each side keeps them readable against the leaves
            for i, ch in enumerate(" " + text + " ", start=-1):
                if 0 <= x + i < cols and 0 <= y < rows:
                    out[(x + i, y)] = (ch, color)

        for f in self.flies:
            if f.rest > 0:
                wings = "}{" if math.sin(f.t * 2.5) > 0.85 else ")("
                bob = 0
            else:
                wings = "}{" if int(f.t * 10) % 2 else ")("
                bob = 0.4 * math.sin(f.t * 9)
            put(int(round(f.x)), int(round(f.y + bob)), wings, f.color)
        for b in self.birds:
            sitting = b.state == "sit"
            bob = 0 if sitting else 0.35 * math.sin(b.t * 5)
            put(int(round(b.x)) - 1, int(round(b.y + bob)), b.glyph(b.y >= rows - 1), b.color)


# ------------------------------------------------------------------ garden

class LivingGarden(Garden):
    """The tree plus its season, the wind and the visitors.

    Drop-in replacement for :class:`Garden`: the same ``cells``, ``version``,
    ``update`` and ``resize``.
    """

    def __init__(self, cols: int, rows: int, grow_minutes: float = 40.0, seed: int | None = None,
                 season: str = "auto", hemisphere: str = "auto", animals: bool = True, wind: bool = True,
                 now: _dt.datetime | None = None):
        super().__init__(cols, rows, grow_minutes, seed)
        self.season, self.season_progress = resolve_season(season, hemisphere, now)
        self.animals, self.windy = animals, wind
        self._clock = (lambda: now) if now else None
        self._setup()

    def _setup(self) -> None:
        rng = random.Random(self.rng.random())
        cols, rows = self.plant.cols, self.plant.rows
        self.look = SeasonLook(self.season, self.season_progress, rng)
        self.wind = Wind(rng, cols, self.season, self.windy)
        self.weather = Weather(rng, cols, rows, self.season, self.season_progress, self.wind)
        self.visitors = Visitors(rng, cols, rows, self.season, self.animals, self._clock)
        self._base: dict = {}
        self._sources: list = []
        self._plant_dirty = True
        self._cells: dict = {}
        self._cells_version = -1

    def resize(self, cols: int, rows: int) -> None:
        old = self.plant
        super().resize(cols, rows)
        if self.plant is not old:
            self._setup()

    def update(self, dt: float) -> None:
        before = self.version
        super().update(dt)
        if self.version != before:
            self._plant_dirty = True
        base = self._season_cells()
        changed = self.wind.update(dt)
        changed |= self.weather.update(dt, base, self._sources)
        changed |= self.visitors.update(dt, base, self.plant.progress)
        if changed and self.version == before:
            self.version += 1

    # -- composing --------------------------------------------------------- #

    def _season_cells(self) -> dict:
        """The plant's cells as they look this season (cached until the plant changes)."""
        if not self._plant_dirty:
            return self._base
        self._plant_dirty = False
        src = self.plant.cells
        look = self.look
        if look.season == "summer":
            self._base, self._sources = src, []
            return src
        base: dict = {}
        sources = []
        for pos, (ch, color) in src.items():
            if color.startswith(("leaf", "ivy")):
                cell = look.leaf(pos[0], pos[1], ch, color)
                if cell is None:
                    continue
                base[pos] = cell
                if cell[1].startswith("aut_"):
                    sources.append(pos)
            else:
                base[pos] = (ch, color)
        if look.season == "winter":  # snow settles on whatever faces the sky
            salt = look.salt
            for (x, y), (ch, color) in list(base.items()):
                if (x, y - 1) in base:
                    continue
                if color in ("win_leaf", "leaf_deep", "ivy") or color.startswith("leaf"):
                    if _hash(x, y, salt + 7) < 0.8:
                        base[(x, y)] = (ch, "snow")
                elif color == "soil_light":
                    base[(x, y)] = (ch, "snow")
                elif color.startswith(("wood", "stem")) and ch == "~":
                    base[(x, y)] = (ch, "snow_dim")
        self._base, self._sources = base, sources
        return base

    def _ruffle(self, out: dict) -> None:
        """Gusts flip the leaves they pass over."""
        wind = self.wind
        cols, rows = self.plant.cols, self.plant.rows
        tick = int(wind.t * 6)
        green = self.season in ("spring", "summer")
        for gx, _v, w, _s in wind.gusts:
            for x in range(max(0, int(gx - w)), min(cols, int(gx + w) + 1)):
                s = abs(wind.at(x))
                if s < 0.25:
                    continue
                for y in range(rows):
                    cell = out.get((x, y))
                    if cell is None:
                        continue
                    ch, color = cell
                    if color.startswith("vine") and ch in "()":
                        if _hash(x, y, tick) < s * 0.7:
                            out[(x, y)] = (")" if ch == "(" else "(", color)
                    elif color.startswith(LEAFY) and _hash(x, y, tick) < s * 0.55:
                        if green and not color.startswith("ivy"):
                            out[(x, y)] = (ch, "wind")  # pale undersides
                        else:
                            out[(x, y)] = ("~'`"[int(_hash(y, x, tick) * 2.999)], color)

    @property
    def cells(self):
        if self._cells_version != self.version or self._plant_dirty:
            self._cells_version = self.version
            out = dict(self._season_cells())
            if self.wind.gusts:
                self._ruffle(out)
            self.weather.draw(out)
            self.visitors.draw(out)
            self._cells = out
        return self._cells
