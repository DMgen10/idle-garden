"""Run the tree inside a terminal (curses). Any key exits."""

from __future__ import annotations

import curses
import time

from .config import Config
from .plants import PALETTE, Garden


def _rgb_to_256(r: int, g: int, b: int) -> int:
    def q(v: int) -> int:
        return 0 if v < 48 else 1 if v < 115 else (v - 35) // 40

    return 16 + 36 * q(r) + 6 * q(g) + q(b)


def _rgb_to_8(r: int, g: int, b: int) -> int:
    bits = (1 if r > 110 else 0) | (2 if g > 110 else 0) | (4 if b > 110 else 0)
    # curses order: black red green yellow blue magenta cyan white
    return [curses.COLOR_BLACK, curses.COLOR_RED, curses.COLOR_GREEN, curses.COLOR_YELLOW,
            curses.COLOR_BLUE, curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_WHITE][bits]


def _main(stdscr, cfg: Config) -> None:
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)
    pairs: dict[str, int] = {}
    if curses.has_colors():
        curses.start_color()
        try:
            curses.use_default_colors()
            bg = -1
        except curses.error:
            bg = curses.COLOR_BLACK
        conv = _rgb_to_256 if curses.COLORS >= 256 else _rgb_to_8
        for i, (name, rgb) in enumerate(PALETTE.items(), start=1):
            if i >= curses.COLOR_PAIRS:
                break
            curses.init_pair(i, conv(*rgb), bg)
            pairs[name] = i

    rows, cols = stdscr.getmaxyx()
    garden = Garden(cols - 1, rows, cfg.grow_minutes)
    last, version = time.monotonic(), -1
    frame = 1.0 / max(1, cfg.fps)
    while True:
        key = stdscr.getch()
        if key == curses.KEY_RESIZE:
            rows, cols = stdscr.getmaxyx()
            garden.resize(cols - 1, rows)
        elif key != -1:
            break
        now = time.monotonic()
        garden.update(min(now - last, 0.5))
        last = now
        if garden.version != version:
            version = garden.version
            stdscr.erase()
            for (x, y), (ch, color) in list(garden.cells.items()):
                if y < rows and x < cols - 1:
                    try:
                        stdscr.addstr(y, x, ch, curses.color_pair(pairs.get(color, 0)) | curses.A_BOLD)
                    except curses.error:
                        pass
            stdscr.refresh()
        time.sleep(frame)


def run_terminal(cfg: Config) -> None:
    try:
        curses.wrapper(_main, cfg)
    except KeyboardInterrupt:
        pass
