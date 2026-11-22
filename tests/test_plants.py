import random
import tempfile
import unittest
from pathlib import Path

from idle_garden.config import Config, load_config
from idle_garden.plants import PALETTE, Garden, Plant


class PlantTests(unittest.TestCase):
    def test_grows_and_fills_screen(self):
        for seed in range(8):
            for cols, rows in ((40, 15), (120, 40), (240, 70)):
                p = Plant(cols, rows, random.Random(seed), grow_seconds=60).grow_all()
                self.assertTrue(p.done)
                self.assertGreater(len(p.cells) / (p.cols * p.rows), 0.75)
                for (x, y), (ch, color) in p.cells.items():
                    self.assertTrue(0 <= x < p.cols and 0 <= y < p.rows)
                    self.assertEqual(len(ch), 1)
                    self.assertIn(color, PALETTE)

    def test_grows_slowly_from_a_sprout(self):
        p = Plant(120, 40, random.Random(1), grow_seconds=600)
        ground = len(p.cells)
        p.update(5)
        self.assertLess(len(p.cells) - ground, 10, "should start as a tiny sprout")
        p.update(295)
        self.assertFalse(p.done)
        self.assertLess(p.progress, 0.9)

    def test_plant_grows_from_earth_in_the_centre(self):
        p = Plant(120, 40, random.Random(2))
        self.assertEqual(p.cx, 60)
        self.assertTrue(any(c.startswith("soil") for _, c in p.cells.values()))

    def test_every_plant_is_different(self):
        shapes = {Plant(120, 40, random.Random(seed), grow_seconds=60).grow_all().to_text() for seed in range(5)}
        self.assertEqual(len(shapes), 5)

    def test_has_vines(self):
        p = Plant(160, 50, random.Random(7), grow_seconds=60).grow_all()
        self.assertTrue(any(color.startswith(("vine", "ivy")) for _, color in p.cells.values()))

    def test_keeps_living_after_full_growth(self):
        p = Plant(80, 30, random.Random(3), grow_seconds=1).grow_all()
        before = dict(p.cells)
        changed = sum(p.update(0.5) for _ in range(20))
        self.assertGreater(changed, 0)
        self.assertNotEqual(before, p.cells)

    def test_garden_resize(self):
        g = Garden(80, 30, grow_minutes=0.1, seed=1)
        g.update(1)
        g.resize(100, 40)
        self.assertEqual(g.grid_cols, 100)

    def test_config_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.ini"
            path.write_text("[garden]\ntimeout = 30  # comment\ngrow_minutes = 3\nkeep_screen_on = yes\nfont_size = big\n")
            cfg = load_config(path)
        self.assertEqual(cfg.timeout, 30)
        self.assertEqual(cfg.grow_minutes, 3)
        self.assertTrue(cfg.keep_screen_on)
        self.assertEqual(cfg.font_size, Config().font_size)


if __name__ == "__main__":
    unittest.main()
