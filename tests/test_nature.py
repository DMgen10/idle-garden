import datetime as dt
import unittest

from idle_garden import nature
from idle_garden.config import Config
from idle_garden.nature import LivingGarden, detect_hemisphere, resolve_season, season_on
from idle_garden.themes import DARK, LIGHT

NOON = dt.datetime(2026, 11, 24, 13, 0)


def grown(season, seed=1, cols=100, rows=34, seconds=200, **kw):
    g = LivingGarden(cols, rows, grow_minutes=1, seed=seed, season=season, now=NOON, **kw)
    for _ in range(int(seconds * 10)):
        g.update(0.1)
    return g


class SeasonTests(unittest.TestCase):
    def test_season_from_date(self):
        self.assertEqual(season_on(dt.date(2026, 11, 24))[0], "autumn")
        self.assertEqual(season_on(dt.date(2026, 1, 10))[0], "winter")
        self.assertEqual(season_on(dt.date(2026, 4, 1))[0], "spring")
        self.assertEqual(season_on(dt.date(2026, 7, 1))[0], "summer")
        self.assertEqual(season_on(dt.date(2026, 11, 24), "south")[0], "spring")
        self.assertEqual(season_on(dt.date(2026, 1, 10), "south")[0], "summer")

    def test_season_progress(self):
        self.assertAlmostEqual(season_on(dt.date(2026, 9, 1))[1], 0.0)
        self.assertGreater(season_on(dt.date(2026, 11, 24))[1], 0.9)
        self.assertLess(season_on(dt.date(2027, 1, 1))[1], 0.4)  # winter spans the new year

    def test_explicit_season_wins(self):
        self.assertEqual(resolve_season("winter", "north", NOON)[0], "winter")
        self.assertEqual(resolve_season("fall", "north", dt.datetime(2026, 5, 1))[0], "autumn")
        self.assertEqual(resolve_season("auto", "south", NOON)[0], "spring")

    def test_hemisphere_from_time_zone(self):
        self.assertEqual(detect_hemisphere("Europe/Moscow"), "north")
        self.assertEqual(detect_hemisphere("Australia/Sydney"), "south")
        self.assertEqual(detect_hemisphere("America/Argentina/Buenos_Aires"), "south")
        self.assertEqual(detect_hemisphere("AUS Eastern Standard Time"), "south")
        self.assertEqual(detect_hemisphere("Russian Standard Time"), "north")
        self.assertEqual(detect_hemisphere(""), "north")

    def test_config_has_season_options(self):
        opts = nature.garden_options(Config())
        self.assertEqual(opts, {"season": "auto", "hemisphere": "auto", "animals": True, "wind": True})


class LivingGardenTests(unittest.TestCase):
    def check_cells(self, g):
        for (x, y), (ch, color) in g.cells.items():
            self.assertTrue(0 <= x < g.grid_cols and 0 <= y < g.grid_rows, (x, y))
            self.assertEqual(len(ch), 1)
            self.assertIn(color, DARK)
            self.assertIn(color, LIGHT)

    def test_every_season_draws_valid_cells(self):
        for season in nature.SEASONS:
            self.check_cells(grown(season, seconds=120))

    def test_autumn_leaves_turn_and_fall(self):
        g = grown("autumn")
        colors = [c for _, c in g.cells.values()]
        self.assertTrue(any(c.startswith("aut_") for c in colors))
        self.assertTrue(g.weather.parts or g.weather.litter)
        self.assertLess(len(g._season_cells()), len(g.plant.cells))  # some leaves have fallen
        summer = grown("summer")
        self.assertEqual(len(summer._season_cells()), len(summer.plant.cells))

    def test_winter_is_bare_and_snowy(self):
        g = grown("winter")
        base = g._season_cells()
        self.assertLess(len(base), len(g.plant.cells) * 0.75)
        self.assertTrue(any(c == "snow" for _, c in base.values()))
        self.assertTrue(any(c == "snow" for _, c in g.weather.litter.values()))

    def test_birds_come_and_go(self):
        g = LivingGarden(100, 34, grow_minutes=1, seed=4, season="summer", now=NOON)
        sat, came = False, 0
        for _ in range(6000):
            g.update(0.1)
            came = max(came, len(g.visitors.birds))
            sat |= any(b.state == "sit" for b in g.visitors.birds)
        self.assertGreater(came, 0)
        self.assertTrue(sat)

    def test_butterflies_only_in_spring_and_summer(self):
        self.assertTrue(grown("summer", seconds=300).visitors.flies)
        self.assertFalse(grown("winter", seconds=300).visitors.flies)

    def test_no_animals_no_wind(self):
        g = grown("summer", seconds=200, animals=False, wind=False)
        self.assertFalse(g.visitors.birds or g.visitors.flies)
        self.assertFalse(g.wind.gusts)

    def test_resize_starts_over(self):
        g = grown("autumn", seconds=30)
        g.resize(60, 20)
        self.assertEqual((g.grid_cols, g.grid_rows), (60, 20))
        g.update(1)
        self.check_cells(g)

    def test_keeps_changing_when_grown(self):
        g = grown("winter", seconds=150)
        before = g.version
        for _ in range(30):
            g.update(0.1)
        self.assertGreater(g.version, before)


if __name__ == "__main__":
    unittest.main()
