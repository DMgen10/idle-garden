"""A procedural ASCII tree that slowly grows over the whole screen.

Pure Python, no dependencies, so every frontend (GTK window, terminal, tests,
SVG export) shares it.

How it works
------------
1. A small mound of earth is drawn at the bottom centre of the screen.
2. The plant's skeleton is computed up front with the *space colonization*
   algorithm: points are scattered over the whole screen and the stems grow
   towards them, so the plant naturally spreads until it covers everything.
3. Leaves are placed on the thin twigs, then foliage spreads into the
   remaining gaps.
4. Every character gets a "birth time". The plant is revealed slowly over
   ``grow_seconds``. New leaves appear bright and darken as they mature.
5. Once the screen is overgrown, random leaves keep being replaced by fresh
   young ones, so the plant looks alive.

``Garden.cells`` maps ``(x, y)`` to ``(char, color)``; ``color`` is a key of
:data:`PALETTE`.
"""

from __future__ import annotations

import heapq
import math
import random
from collections import defaultdict

# name -> (r, g, b)
PALETTE: dict[str, tuple[int, int, int]] = {
    "leaf_new": (200, 240, 110),
    "leaf_young": (150, 215, 90),
    "leaf_light": (104, 190, 80),
    "leaf": (66, 158, 64),
    "leaf_dark": (40, 120, 52),
    "leaf_deep": (28, 90, 44),
    "stem_new": (170, 215, 120),
    "stem_light": (120, 175, 85),
    "stem": (92, 140, 64),
    "stem_dark": (110, 92, 52),
    "wood": (140, 100, 62),
    "vine": (118, 160, 78),
    "vine_dark": (84, 128, 60),
    "ivy": (52, 130, 84),
    "ivy_light": (96, 176, 104),
    "wood_dark": (105, 72, 44),
    "soil_light": (170, 122, 78),
    "soil": (132, 92, 58),
    "soil_dark": (96, 66, 44),
    "pebble": (150, 146, 138),
}

LEAF_CHARS = "&&&&@@%%**"
FILL_CHARS = "&&&%%@@*"
IVY_CHARS = "&&%%*"

# how a cell looks while it is young: (seconds, colour) stages
LEAF_STAGES = ((2.5, "leaf_new"), (7.0, "leaf_young"), (14.0, "leaf_light"))
STEM_STAGES = ((3.0, "stem_new"), (9.0, "stem_light"))

ASPECT = 0.5  # a character cell is about twice as tall as it is wide


def _stage_color(stages, age: float, final: str) -> str:
    for limit, color in stages:
        if age < limit:
            return color
    return final


def _stem_char(dx: float, dy: float) -> str:
    """Pick a line character for a direction given in cell units."""
    ang = math.degrees(math.atan2(-dy, dx * ASPECT)) % 180
    if ang < 25 or ang >= 155:
        return "~"
    if ang < 65:
        return "/"
    if ang < 115:
        return "|"
    return "\\"


class Plant:
    """One plant growing from a patch of earth. Call :meth:`update` with elapsed seconds."""

    def __init__(self, cols: int, rows: int, rng: random.Random | None = None,
                 grow_seconds: float = 2400.0):
        self.cols = max(30, int(cols))
        self.rows = max(16, int(rows))
        self.rng = rng or random.Random()
        self.grow_seconds = max(1.0, grow_seconds)
        self.cells: dict[tuple[int, int], tuple[str, str]] = {}
        self.blocked: set[tuple[int, int]] = set()  # ground cells

        self._build_ground()
        events = self._build_plant()
        events.sort(key=lambda e: e[0])
        self.events = events
        self.t_max = events[-1][0] if events else 1.0
        self.idx = 0

        self.clock = 0.0
        self.done = False
        self.young: dict[tuple[int, int], tuple[float, str, str]] = {}
        self.leaf_cells: list[tuple[int, int]] = []
        self.final_color: dict[tuple[int, int], str] = {}
        self.temp_cells: set[tuple[int, int]] = set()
        self._alive_acc = 0.0
        # growth comes in spurts and lulls, different for every plant
        self.growth_clock = 0.0
        self._waves = [(self.rng.uniform(0.35, 0.6), 2 * math.pi / self.rng.uniform(40, 120), self.rng.uniform(0, 6.3)),
                       (self.rng.uniform(0.2, 0.4), 2 * math.pi / self.rng.uniform(180, 500), self.rng.uniform(0, 6.3))]

    # --------------------------------------------------------------- ground

    def _build_ground(self) -> None:
        """A small dome of earth at the bottom centre the plant sprouts from."""
        c, r, rng = self.cols, self.rows, self.rng
        half = max(4, min(12, c // 24))
        mh = max(2, min(3, r // 20))
        self.cx = c // 2
        top = r - mh

        def put(x, y, ch, color):
            if 0 <= x < c and 0 <= y < r:
                self.cells[(x, y)] = (ch, color)
                self.blocked.add((x, y))

        prev = -1
        for i in range(mh):
            y = top + i
            hw = max(2, int(round(half * math.sqrt(max(0.0, 1 - ((mh - 1 - i) / mh) ** 2)))))
            for dx in range(-hw, hw + 1):
                x = self.cx + dx
                exposed = i == 0 or abs(dx) > prev
                if dx == -hw:
                    put(x, y, "." if i == 0 else "/", "soil_light")
                elif dx == hw:
                    put(x, y, "." if i == 0 else "\\", "soil_light")
                elif exposed:
                    put(x, y, rng.choice("~-~-'`" if i == 0 else "_-'"), "soil_light")
                elif rng.random() < 0.05:
                    put(x, y, rng.choice("oO"), "pebble")
                else:
                    put(x, y, rng.choice(".:;,'`~"), rng.choice(("soil", "soil", "soil_dark")))
            prev = hw
        # a little loose earth on either side
        for side in (-1, 1):
            for k in range(1, rng.randint(3, 6)):
                put(self.cx + side * (prev + k), r - 1, rng.choice("_.,"), "soil_dark")
        self.soil_y = top

    def _in_ground(self, x: int, y: int) -> bool:
        return (x, y) in self.blocked

    # ------------------------------------------------------- skeleton growth

    def _build_plant(self):
        rng = self.rng
        cols, rows = self.cols, self.rows
        W, H = cols * ASPECT, float(rows)

        # Every tree gets its own character.
        R = max(6.0, min(10.0, H / 5)) * rng.uniform(0.8, 1.2)  # influence radius
        KILL = 1.6
        STEP = 1.0
        spacing = rng.uniform(2.3, 3.0)
        B = R  # bucket size
        jitter = rng.uniform(0.25, 0.55)  # how gnarled the branches are
        up = rng.uniform(0.1, 0.4)  # how strongly it reaches for the light
        lean = rng.uniform(-0.2, 0.2)  # trunk lean

        # Attraction points over the whole screen except the ground: an even
        # sprinkle plus a few dense clumps, so every crown is lopsided its own way.
        attr: dict[int, tuple[float, float]] = {}
        n_attr = int(W * H / (spacing * spacing))
        clumps = [(rng.uniform(0.1, 0.9) * W, rng.uniform(0.05, 0.7) * H, rng.uniform(0.08, 0.2) * W)
                  for _ in range(rng.randint(2, 6))]
        clumped = rng.uniform(0.2, 0.5)
        for i in range(n_attr):
            for _ in range(10):
                if rng.random() < clumped:
                    mx, my, sd = rng.choice(clumps)
                    ax, ay = rng.gauss(mx, sd), rng.gauss(my, sd * 0.6)
                else:
                    ax, ay = rng.uniform(0.5, W - 0.5), rng.uniform(0.5, H - 0.5)
                if 0.5 <= ax <= W - 0.5 and 0.5 <= ay <= H - 0.5 and not self._in_ground(int(ax / ASPECT), int(ay)):
                    attr[i] = (ax, ay)
                    break
        buckets: dict[tuple[int, int], set[int]] = defaultdict(set)
        for i, (ax, ay) in attr.items():
            buckets[(int(ax // B), int(ay // B))].add(i)
        best: dict[int, tuple[int, float]] = {}

        nx_: list[float] = []
        ny_: list[float] = []
        parent: list[int] = []
        gen: list[float] = []  # birth time of each node
        start: list[float] = []  # earliest time a node may sprout side shoots
        vigor: list[float] = []  # growth speed of the branch a node belongs to
        kids: list[int] = []
        occupied: set[tuple[int, int]] = set()

        def cell_of(x, y):
            return int(round(x / ASPECT)), int(round(y))

        def add_node(x, y, p):
            i = len(nx_)
            nx_.append(x)
            ny_.append(y)
            parent.append(p)
            if p < 0:
                t, v = 0.0, 1.0
            elif kids[p] == 0:  # the same branch carries on
                v = vigor[p]
                t = max(gen[p], start[p]) + 1.0 / v
                if rng.random() < 0.03:  # a short rest now and then
                    t += rng.expovariate(1 / 3.0)
            else:  # a new side shoot: its own speed, maybe dormant for a while
                v = min(2.5, max(0.35, rng.lognormvariate(0, 0.45)))
                t = max(gen[p], start[p]) + 1.0 / v
                if rng.random() < 0.45:
                    t += rng.expovariate(1 / 6.0)
            if p >= 0:
                kids[p] += 1
            gen.append(t)
            start.append(t)
            vigor.append(v)
            kids.append(0)
            occupied.add(cell_of(x, y))
            bx, by = int(x // B), int(y // B)
            for gx in (bx - 1, bx, bx + 1):
                for gy in (by - 1, by, by + 1):
                    bucket = buckets.get((gx, gy))
                    if not bucket:
                        continue
                    for a in list(bucket):
                        ax, ay = attr[a]
                        d = math.hypot(ax - x, ay - y)
                        if d < KILL:
                            bucket.discard(a)
                            del attr[a]
                            best.pop(a, None)
                        elif d < R and d < best.get(a, (0, 1e9))[1]:
                            best[a] = (i, d)
            return i

        def free(x, y):
            cx, cy = cell_of(x, y)
            return (0 <= cx < cols and 0 <= cy < rows and (cx, cy) not in occupied
                    and not self._in_ground(cx, cy))

        # the trunk: a tall, gently wavering stem straight up out of the soil
        x, y = self.cx * ASPECT, float(self.soil_y)
        last = add_node(x, y, -1)
        sprout_len = max(6, int(H * rng.uniform(0.38, 0.62)))
        wobble = lean
        for _ in range(sprout_len):
            wobble = max(-0.35, min(0.35, wobble + rng.uniform(-0.1, 0.1) + (lean - wobble) * 0.1))
            x, y = x + wobble * 0.5, y - STEP
            if not free(x, y):
                break
            last = add_node(x, y, last)
        # The trunk rises first. Its lower part stays bare (it can only sprout
        # as a last resort); the crown branches out from the top downwards.
        L = len(nx_)
        self._sprout_len = L
        bare = int(L * 0.55)
        self._bare = bare
        for k in range(L):
            start[k] = L + (L - k) * 0.8
        bare_locked = True

        fails: dict[int, int] = defaultdict(int)
        for _ in range(4000):
            if not attr:
                break
            pull: dict[int, list] = {}
            for a, (n, _d) in best.items():
                ax, ay = attr[a]
                dx, dy = ax - nx_[n], ay - ny_[n]
                d = math.hypot(dx, dy) or 1.0
                acc = pull.setdefault(n, [0.0, 0.0, []])
                acc[0] += dx / d
                acc[1] += dy / d
                acc[2].append(a)
            if not pull:
                # nothing in range: let the youngest tip reach further
                R *= 1.4
                for a, (ax, ay) in attr.items():
                    bi, bd = -1, R
                    for n in range(len(nx_)):
                        d = math.hypot(ax - nx_[n], ay - ny_[n])
                        if d < bd:
                            bi, bd = n, d
                    if bi >= 0:
                        best[a] = (bi, bd)
                if not best:
                    break
                continue
            grew = False
            for n, (sx, sy, owners) in pull.items():
                if bare_locked and n < bare:
                    continue
                sy -= up * len(owners)  # plants like to grow upward
                d = math.hypot(sx, sy)
                if d < 1e-6:
                    sx, sy, d = rng.uniform(-1, 1), -1.0, 1.0
                ang = rng.gauss(0, jitter)  # gnarled, never perfectly straight
                ca, sa = math.cos(ang), math.sin(ang)
                sx, sy = sx * ca - sy * sa, sx * sa + sy * ca
                gx, gy = nx_[n] + sx / d * STEP, ny_[n] + sy / d * STEP
                if not free(gx, gy):
                    # try a little to the side
                    ang = rng.uniform(-0.9, 0.9)
                    ca, sa = math.cos(ang), math.sin(ang)
                    rx, ry = (sx * ca - sy * sa) / d, (sx * sa + sy * ca) / d
                    gx, gy = nx_[n] + rx * STEP, ny_[n] + ry * STEP
                if free(gx, gy) and 0 <= gx <= W and 0 <= gy <= H:
                    add_node(gx, gy, n)
                    grew = True
                else:
                    fails[n] += 1
                    if fails[n] >= 3:  # give up on these points
                        for a in owners:
                            if a in attr:
                                ax, ay = attr.pop(a)
                                buckets[(int(ax // B), int(ay // B))].discard(a)
                                best.pop(a, None)
            if not grew:
                if not bare_locked:
                    break
                bare_locked = False  # only the bare trunk is left to grow from

        return self._dress(nx_, ny_, parent, gen)

    # -------------------------------------------------- stems, leaves, fill

    def _dress(self, xs, ys, parent, gen):
        rng = self.rng
        n = len(xs)
        desc = [1] * n
        for i in range(n - 1, 0, -1):
            if parent[i] >= 0:
                desc[parent[i]] += desc[i]
        thick_lim = max(12, n * 0.06)
        mid_lim = max(5, n * 0.012)

        events = []  # (t, x, y, char, kind, final colour)
        protected: set[tuple[int, int]] = set()  # leaves never cover these cells
        wood: set[tuple[int, int]] = set()  # trunk and thick branches
        leaf_t: dict[tuple[int, int], float] = {}

        def ok(x, y):
            return 0 <= x < self.cols and 0 <= y < self.rows and (x, y) not in self.blocked

        # stems: draw a line from each node to its parent
        for i in range(1, n):
            p = parent[i]
            x0, y0 = xs[p] / ASPECT, ys[p]
            x1, y1 = xs[i] / ASPECT, ys[i]
            ch = _stem_char(x1 - x0, y1 - y0)
            if desc[i] >= thick_lim or i < self._sprout_len:
                color, thick = "wood_dark", True
            elif desc[i] >= mid_lim:
                color, thick = "wood", True
            else:
                color, thick = "stem_light", False
            steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) + 0.5))
            for s in range(1, steps + 1):
                cx = int(round(x0 + (x1 - x0) * s / steps))
                cy = int(round(y0 + (y1 - y0) * s / steps))
                if ok(cx, cy):
                    events.append((gen[i] + s / steps - 1, cx, cy, ch, "stem", color))
                    if thick:
                        protected.add((cx, cy))
                        wood.add((cx, cy))
            # the lower trunk is two characters wide
            if i <= self._sprout_len * 0.7:
                cx, cy = int(round(x1)) + 1, int(round(y1))
                if ok(cx, cy):
                    events.append((gen[i], cx, cy, ch, "stem", "wood_dark"))
                    protected.add((cx, cy))
                    wood.add((cx, cy))
        # roots flaring out at the base: /||\
        if n > 1:
            rx, ry = int(round(xs[1] / ASPECT)), int(round(ys[1]))
            for cx, ch in ((rx - 1, "/"), (rx + 2, "\\")):
                if ok(cx, ry):
                    events.append((2.0, cx, ry, ch, "stem", "wood_dark"))
                    protected.add((cx, ry))
                    wood.add((cx, ry))
        # keep a little air around the bare trunk so it reads as a tree
        trunk_x: dict[int, int] = {}
        for i in range(1, min(n, self._bare)):
            cx, cy = int(round(xs[i] / ASPECT)), int(round(ys[i]))
            trunk_x[cy] = cx
            protected.update({(cx - 1, cy), (cx + 2, cy)})

        self._add_vines(events, xs, ys, gen, desc, thick_lim, protected, wood, leaf_t, trunk_x)

        def leaf(x, y, t, chars, final):
            if ok(x, y) and (x, y) not in protected and (x, y) not in leaf_t:
                leaf_t[(x, y)] = t
                events.append((t, x, y, rng.choice(chars), "leaf", final))

        # The young sapling carries a few leaves just below its growing tip.
        # On the bare part of the trunk they drop off again as it grows taller.
        side = rng.choice((-1, 1))
        for i in range(2, self._sprout_len, 2):
            cx, cy = int(round(xs[i] / ASPECT)), int(round(ys[i]))
            side = -side
            gone = gen[i] + 7 if i < self._bare else None
            for k in range(1, rng.choice((3, 4, 4)) + 1):
                x, y, t = cx + side * (k + 1), cy - (k >= 3), gen[i] + 0.6 + k * 0.35
                if gone is None:
                    leaf(x, y, t, LEAF_CHARS, rng.choice(("leaf", "leaf_light")))
                elif ok(x, y) and (x, y) not in protected:
                    events.append((t, x, y, rng.choice(LEAF_CHARS), "temp", "leaf"))
                    events.append((gone + k * 0.5, x, y, " ", "gone", ""))

        # leaves on twigs and tips, and along the stems
        for i in range(1, n):
            cx, cy = int(round(xs[i] / ASPECT)), int(round(ys[i]))
            if i < self._bare:
                continue
            if desc[i] <= 4 and rng.random() < 0.7:
                rx = rng.choice((1, 2, 2, 3))
                ry = rng.choice((0, 1, 1))
                t0 = gen[i] + 1.5 + rng.random() * 2.5
                for dy in range(-ry, ry + 1):
                    for dx in range(-rx, rx + 1):
                        if (dx / (rx + 0.5)) ** 2 + (dy / (ry + 0.5)) ** 2 <= 1.0:
                            final = rng.choice(("leaf_light", "leaf", "leaf", "leaf_dark"))
                            leaf(cx + dx, cy + dy, t0 + (abs(dx) + abs(dy)) * 0.3, LEAF_CHARS, final)
            elif desc[i] < thick_lim and rng.random() < 0.55:
                # small leaves along the stems break up long bare lines
                t0 = gen[i] + 1.0 + rng.random() * 2.0
                side = rng.choice((-1, 1))
                if abs(xs[i] - xs[parent[i]]) * 2 > abs(ys[i] - ys[parent[i]]):  # stem runs sideways
                    leaf(cx, cy + side, t0, LEAF_CHARS, "leaf")
                    if rng.random() < 0.5:
                        leaf(cx + rng.choice((-1, 1)), cy + side, t0 + 0.4, LEAF_CHARS, "leaf_light")
                else:
                    leaf(cx + side, cy, t0, LEAF_CHARS, "leaf")
                    leaf(cx + 2 * side, cy, t0 + 0.4, LEAF_CHARS, "leaf_light")
            elif desc[i] >= thick_lim and i >= self._bare and gen[i] % 3 == 0 and rng.random() < 0.8:
                side = rng.choice((-1, 1))
                t0 = gen[i] + 2.0
                for k in range(1, rng.choice((2, 3, 3)) + 1):
                    leaf(cx + side * (k + 1), cy - (k > 2), t0 + k * 0.4, LEAF_CHARS, "leaf")

        # foliage creeps into the gaps until the screen is overgrown
        # some regions fill in quickly, others take their time
        bw, bh = 10, 5
        region = {(bx, by): rng.uniform(0.4, 2.6)
                  for bx in range(self.cols // bw + 2) for by in range(self.rows // bh + 2)}
        heap = [(t, x, y) for (x, y), t in leaf_t.items()]
        heapq.heapify(heap)
        seen = set(leaf_t) | protected
        while heap:
            t, x, y = heapq.heappop(heap)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                q = (x + dx, y + dy)
                if q in seen or not ok(*q):
                    continue
                seen.add(q)
                if rng.random() < 0.12:  # leave a few small gaps
                    continue
                nt = t + (0.5 + rng.expovariate(1 / 1.4)) * region.get((q[0] // bw, q[1] // bh), 1.0)
                final = rng.choice(("leaf_dark", "leaf_dark", "leaf", "leaf_deep"))
                leaf(q[0], q[1], nt, FILL_CHARS, final)
                heapq.heappush(heap, (nt, q[0], q[1]))
        return events

    # ---------------------------------------------------------------- vines

    def _add_vines(self, events, xs, ys, gen, desc, thick_lim, protected, wood, leaf_t, trunk_x):
        """Ivy and creepers: hanging from branches, winding up the trunk,
        crawling over the ground and curling out of the crown."""
        rng = self.rng
        cols, rows = self.cols, self.rows
        n = len(xs)
        t_end = max(gen) if gen else 1.0

        def ok(x, y):
            return 0 <= x < cols and 0 <= y < rows and (x, y) not in self.blocked and (x, y) not in wood

        def ivy_leaf(x, y, t):
            if ok(x, y) and (x, y) not in protected and (x, y) not in leaf_t:
                leaf_t[(x, y)] = t
                events.append((t, x, y, rng.choice(IVY_CHARS), "leaf", rng.choice(("ivy", "ivy", "ivy_light"))))

        def put_vine(x, y, t, ch):
            events.append((t, x, y, ch, "stem", rng.choice(("vine", "vine", "vine_dark"))))
            protected.add((x, y))

        def creeper(x, y, t, ang, length, curl, gravity, speed, leafy):
            """A random walk whose heading keeps swinging: a curly vine."""
            fx, fy = float(x), float(y)
            phase, freq = rng.uniform(0, 6.3), rng.uniform(0.2, 0.6)
            last, side, since, placed = (x, y), rng.choice((-1, 1)), 0, 0
            for _ in range(length * 4):
                ang += curl * math.sin(phase) + rng.gauss(0, 0.1)
                ang += gravity * math.sin(math.pi / 2 - ang)  # droop towards "down"
                phase += freq
                fx += math.cos(ang) * 0.6 / ASPECT
                fy += math.sin(ang) * 0.6
                c = (int(round(fx)), int(round(fy)))
                if c == last:
                    continue
                if not ok(*c):
                    break
                ddx, ddy = c[0] - last[0], c[1] - last[1]
                if ddy == 0:
                    ch = "~"
                elif ddx == 0:
                    ch = ")" if math.sin(phase) > 0 else "("
                else:
                    ch = "/" if ddx * ddy < 0 else "\\"
                t += rng.uniform(0.4, 1.1) / speed
                if rng.random() < 0.04:
                    t += rng.expovariate(1 / 4.0)  # the vine rests, then carries on
                put_vine(c[0], c[1], t, ch)
                since += 1
                if since >= 2 and rng.random() < leafy:
                    since, side = 0, -side
                    if ddx == 0:
                        ivy_leaf(c[0] + side, c[1], t + 0.8)
                        if rng.random() < 0.4:
                            ivy_leaf(c[0] + 2 * side, c[1], t + 1.1)
                    else:
                        ivy_leaf(c[0], c[1] + side, t + 0.8)
                last = c
                placed += 1
                if placed >= length:
                    break
            # a tendril curl at the tip
            if placed > 2 and rng.random() < 0.6:
                tx = last[0] + (1 if math.cos(ang) >= 0 else -1)
                if ok(tx, last[1]) and (tx, last[1]) not in protected:
                    put_vine(tx, last[1], t + 0.8, rng.choice("@@6e"))

        area = cols * rows
        crown = [i for i in range(n) if i >= self._sprout_len and 3 <= desc[i] < thick_lim
                 and ys[i] < rows * 0.75]
        tips = [i for i in range(n) if i >= self._sprout_len and desc[i] <= 2]

        # vines hanging down from the branches
        for _ in range(int(max(2, area / 900) * rng.uniform(0.6, 1.6))):
            if not crown:
                break
            i = rng.choice(crown)
            creeper(int(round(xs[i] / ASPECT)), int(round(ys[i])), gen[i] + rng.uniform(3, 30),
                    math.pi / 2 + rng.gauss(0, 0.5), int(rows * rng.uniform(0.15, 0.55)),
                    rng.uniform(0.04, 0.18), rng.uniform(0.08, 0.2), rng.lognormvariate(0, 0.4), 0.5)

        # curly tendrils sneaking out of the crown
        for _ in range(int(max(3, area / 500) * rng.uniform(0.5, 1.5))):
            if not tips:
                break
            i = rng.choice(tips)
            creeper(int(round(xs[i] / ASPECT)), int(round(ys[i])), gen[i] + rng.uniform(1, 15),
                    rng.uniform(0, 2 * math.pi), rng.randint(4, 12),
                    rng.uniform(0.3, 0.65), 0.02, rng.lognormvariate(0, 0.4), 0.35)

        # creepers crawling sideways over the ground from the mound
        for _ in range(rng.randint(1, 3)):
            d = rng.choice((-1, 1))
            sx = self.cx + d * rng.randint(3, 8)
            creeper(sx, rows - 1, rng.uniform(0.15, 0.6) * t_end, math.pi if d < 0 else 0.0,
                    int(cols * rng.uniform(0.15, 0.35)), rng.uniform(0.05, 0.15), -0.02,
                    rng.lognormvariate(0, 0.3), 0.45)

        # ivy winding up the bare trunk, switching sides as it wraps around
        if trunk_x and rng.random() < 0.85:
            ys_sorted = sorted(trunk_x, reverse=True)  # from the ground upward
            top_k = int(len(ys_sorted) * rng.uniform(0.5, 1.0))
            t = rng.uniform(0.25, 0.5) * t_end
            side, run = rng.choice((-1, 1)), 0
            for k, y in enumerate(ys_sorted[:top_k]):
                x = trunk_x[y] - 1 if side < 0 else trunk_x[y] + 2
                t += rng.uniform(0.5, 1.6)
                if run >= rng.randint(3, 6):  # wrap behind the trunk
                    run, side = 0, -side
                    continue
                if ok(x, y):
                    put_vine(x, y, t, "(" if side < 0 else ")")
                    if rng.random() < 0.55:
                        ivy_leaf(x + side, y, t + 0.7)
                        if rng.random() < 0.4:
                            ivy_leaf(x + 2 * side, y - 1, t + 1.0)
                run += 1

    # -------------------------------------------------------------- runtime

    @property
    def progress(self) -> float:
        """0..1, how much of the plant has been revealed."""
        return self.idx / max(1, len(self.events))

    def update(self, dt: float) -> bool:
        """Advance time; returns True if anything visible changed."""
        changed = False
        if not self.done:
            # integrate the spurts-and-lulls pace in small slices
            left, t = dt, self.clock
            while left > 0:
                h = min(left, 1.0)
                pace = 1.0 + sum(a * math.sin(w * (t + h / 2) + ph) for a, w, ph in self._waves)
                self.growth_clock += h * max(0.15, pace)
                t += h
                left -= h
        self.clock += dt
        if not self.done:
            # slightly faster at the start so the sprout shows up quickly
            frac = min(1.0, self.growth_clock / self.grow_seconds) ** 0.8
            limit = frac * self.t_max
            ev = self.events
            while self.idx < len(ev) and ev[self.idx][0] <= limit:
                _t, x, y, ch, kind, final = ev[self.idx]
                self.idx += 1
                pos = (x, y)
                if kind == "gone":  # a sapling leaf drops off
                    if pos in self.temp_cells:
                        self.temp_cells.discard(pos)
                        self.cells.pop(pos, None)
                        self.young.pop(pos, None)
                        self.final_color.pop(pos, None)
                        changed = True
                    continue
                if kind == "temp":
                    self.temp_cells.add(pos)
                    kind = "leaf"
                else:
                    self.temp_cells.discard(pos)
                    if kind == "leaf":
                        self.leaf_cells.append(pos)
                stages = LEAF_STAGES if kind == "leaf" else STEM_STAGES
                self.cells[pos] = (ch, stages[0][1])
                self.young[pos] = (self.clock, kind, final)
                self.final_color[pos] = final
                changed = True
            if self.idx >= len(ev):
                self.done = True
        else:
            changed |= self._live(dt)

        for pos, (born, kind, final) in list(self.young.items()):
            stages = LEAF_STAGES if kind == "leaf" else STEM_STAGES
            color = _stage_color(stages, self.clock - born, final)
            ch = self.cells[pos][0]
            if color != self.cells[pos][1]:
                self.cells[pos] = (ch, color)
                changed = True
            if color == final:
                del self.young[pos]
        return changed

    def _live(self, dt: float) -> bool:
        """After the screen is overgrown, old leaves are replaced by new ones."""
        if not self.leaf_cells:
            return False
        per_second = max(1.5, len(self.leaf_cells) / 700)
        self._alive_acc += dt * per_second
        changed = False
        while self._alive_acc >= 1.0:
            self._alive_acc -= 1.0
            x, y = self.rng.choice(self.leaf_cells)
            # a new leaf often unfolds next to another young one
            for dx, dy in ((0, 0),) + tuple(
                    (self.rng.randint(-2, 2), self.rng.randint(-1, 1)) for _ in range(self.rng.randint(0, 3))):
                pos = (x + dx, y + dy)
                if pos in self.final_color and self.cells.get(pos, ("", "stem"))[1].startswith("leaf"):
                    if pos in self.young:
                        continue
                    self.cells[pos] = (self.rng.choice(LEAF_CHARS), LEAF_STAGES[0][1])
                    self.young[pos] = (self.clock, "leaf", self.final_color[pos])
                    changed = True
        return changed

    def grow_all(self) -> "Plant":
        """Reveal everything at once (tests, previews)."""
        while not self.done:
            self.update(self.grow_seconds)
        self.update(60)
        return self

    def to_text(self) -> str:
        return "\n".join(
            "".join(self.cells.get((x, y), (" ",))[0] for x in range(self.cols)).rstrip()
            for y in range(self.rows)
        )


class Garden:
    """What the frontends talk to: one plant that grows and then lives on."""

    def __init__(self, cols: int, rows: int, grow_minutes: float = 40.0, seed: int | None = None):
        self.grow_seconds = max(0.05, grow_minutes) * 60
        self.rng = random.Random(seed)
        self.cols, self.rows = cols, rows
        self.plant = Plant(cols, rows, self.rng, self.grow_seconds)
        self.version = 0

    def resize(self, cols: int, rows: int) -> None:
        if (cols, rows) != (self.cols, self.rows):
            self.cols, self.rows = cols, rows
            self.plant = Plant(cols, rows, self.rng, self.grow_seconds)
            self.version += 1

    def update(self, dt: float) -> None:
        if self.plant.update(dt):
            self.version += 1

    @property
    def cells(self):
        return self.plant.cells

    @property
    def grid_cols(self) -> int:
        return self.plant.cols

    @property
    def grid_rows(self) -> int:
        return self.plant.rows
