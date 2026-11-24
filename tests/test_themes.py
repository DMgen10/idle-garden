import tempfile
import unittest
from pathlib import Path
from unittest import mock

from idle_garden import themes
from idle_garden.config import Config, load_config
from idle_garden.plants import PALETTE


class ThemeTests(unittest.TestCase):
    def test_both_themes_know_every_colour(self):
        from idle_garden.nature import COLORS

        for name, palette in themes.THEMES.items():
            self.assertEqual(set(palette), set(PALETTE) | set(COLORS), name)

    def test_light_theme_is_readable_on_light_background(self):
        bg = themes.hex_to_rgb(themes.DEFAULT_BACKGROUND["light"])

        def lum(rgb):
            def ch(v):
                v /= 255
                return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
            r, g, b = (ch(v) for v in rgb)
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        for name, rgb in themes.LIGHT.items():
            contrast = (lum(bg) + 0.05) / (lum(rgb) + 0.05)
            self.assertGreater(contrast, 2.5, name)

    def test_explicit_theme_wins(self):
        with mock.patch.object(themes, "detect_system_theme", return_value="dark"):
            self.assertEqual(themes.resolve_theme("light"), "light")
            self.assertEqual(themes.resolve_theme("auto"), "dark")

    def test_auto_follows_system_and_defaults_to_dark(self):
        cfg = Config()
        with mock.patch.object(themes, "detect_system_theme", return_value="light"):
            name, palette, bg = themes.theme_colors(cfg)
        self.assertEqual((name, bg), ("light", (244, 241, 232)))
        self.assertIs(palette, themes.LIGHT)
        with mock.patch.object(themes, "detect_system_theme", return_value=None):
            self.assertEqual(themes.theme_colors(cfg)[0], "dark")

    def test_gnome_settings(self):
        answers = {"color-scheme": "'prefer-dark'", "gtk-theme": "'Yaru'"}
        with mock.patch.object(themes, "_run", side_effect=lambda cmd: answers[cmd[-1]]):
            self.assertEqual(themes._linux_gsettings(), "dark")
        answers = {"color-scheme": "'default'", "gtk-theme": "'Yaru-dark'"}  # Ubuntu 20.04
        with mock.patch.object(themes, "_run", side_effect=lambda cmd: answers[cmd[-1]]):
            self.assertEqual(themes._linux_gsettings(), "dark")
        answers = {"color-scheme": "'prefer-light'", "gtk-theme": "'Yaru-dark'"}
        with mock.patch.object(themes, "_run", side_effect=lambda cmd: answers[cmd[-1]]):
            self.assertEqual(themes._linux_gsettings(), "light")

    def test_old_background_setting_still_works(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.ini"
            path.write_text("[garden]\nbackground = #101010\ntheme = light\n")
            cfg = load_config(path)
        self.assertEqual(cfg.dark_background, "#101010")
        self.assertEqual(cfg.light_background, Config().light_background)
        self.assertEqual(cfg.theme, "light")

    def test_hex(self):
        self.assertEqual(themes.hex_to_rgb("#fff"), (255, 255, 255))
        self.assertEqual(themes.hex_to_rgb("nonsense", (1, 2, 3)), (1, 2, 3))


class WindowsSourcesTests(unittest.TestCase):
    def test_windows_modules_compile(self):
        import py_compile

        root = Path(__file__).resolve().parent.parent / "idle_garden"
        for name in ("winscreen.py", "winsetup.py"):
            py_compile.compile(str(root / name), doraise=True)


if __name__ == "__main__":
    unittest.main()
