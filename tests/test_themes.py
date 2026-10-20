"""Темы подразделений: одинаковые ключи палитр, корректные эмблемы"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import themes  # noqa: E402

HEX = re.compile(r"^#[0-9a-f]{6}$")
ROLES = {"fill", "cut", "mark", "eye", "dark", "fold"}


class ThemesTest(unittest.TestCase):
    def test_order_matches_themes(self):
        self.assertEqual(sorted(themes.THEME_ORDER), sorted(themes.THEMES))
        self.assertIn(themes.DEFAULT_THEME, themes.THEMES)

    def test_palettes_have_same_keys(self):
        reference = set(themes.THEMES[themes.DEFAULT_THEME]["colors"])
        for key, theme in themes.THEMES.items():
            with self.subTest(theme=key):
                self.assertEqual(set(theme["colors"]), reference)
                for name, value in theme["colors"].items():
                    self.assertRegex(value, HEX, f"{key}.{name}")

    def test_texts_present(self):
        for key, theme in themes.THEMES.items():
            for field in ("name", "short", "of", "title", "watermark"):
                with self.subTest(theme=key, field=field):
                    self.assertTrue(theme[field].strip())

    def test_emblems_valid(self):
        for key, theme in themes.THEMES.items():
            with self.subTest(theme=key):
                self.assertTrue(theme["emblem"])
                for role, points in theme["emblem"]:
                    self.assertIn(role, ROLES)
                    self.assertGreaterEqual(len(points), 3)
                    for x, y in points:
                        self.assertTrue(0 <= x <= 100 and 0 <= y <= 100, (key, x, y))

    def test_emblem_colors_cover_roles(self):
        colors = themes.THEMES["bko"]["colors"]
        self.assertEqual(set(themes.emblem_colors(colors, "#000000")), ROLES)
        self.assertEqual(set(themes.watermark_colors(colors, "#000000")), ROLES)

    def test_unknown_key_falls_back(self):
        self.assertEqual(themes.theme_key("нет такой"), themes.DEFAULT_THEME)
        self.assertEqual(themes.theme_key(None), themes.DEFAULT_THEME)
        self.assertIs(themes.get_theme("нет такой"), themes.THEMES[themes.DEFAULT_THEME])
        self.assertEqual(themes.theme_key("marines"), "marines")


if __name__ == "__main__":
    unittest.main()
