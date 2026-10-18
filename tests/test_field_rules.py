"""Тесты правил из методички: подсказки и названия орудий"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import field_rules as fr  # noqa: E402

MORTAR, SLEDGE = "Миномёт", "Кувалда"


def texts(items):
    return [text for _, text in items]


class AdvisoriesTest(unittest.TestCase):
    def test_only_dispersion_when_flat(self):
        items = fr.advisories(MORTAR, 1, 1000, 100, 120, correction_on=False)
        self.assertEqual(len(items), 1)
        self.assertIn("Разброс до 20 м", items[0][1])
        self.assertEqual(items[0][0], "info")

    def test_height_recommended_and_required(self):
        rec = fr.advisories(MORTAR, 1, 1000, 100, 160, correction_on=False)
        self.assertEqual(rec[0], ("info", "Перепад высот 60 м — поправка на превышение рекомендуется"))
        req = fr.advisories(MORTAR, 1, 1000, 100, 0, correction_on=False)
        self.assertEqual(req[0], ("warn", "Перепад высот 100 м — поправка на превышение обязательна"))

    def test_no_height_hint_when_correction_on(self):
        self.assertFalse(any("Перепад" in t for t in texts(fr.advisories(MORTAR, 1, 1000, 0, 500, True))))

    def test_no_height_hint_without_heights(self):
        self.assertEqual(len(fr.advisories(MORTAR, 1, 1000, None, None, False)), 1)

    def test_high_target_needs_charge_2(self):
        warn = [t for t in texts(fr.advisories(MORTAR, 1, 1000, 0, 300, True)) if "заряд 2" in t]
        self.assertEqual(len(warn), 1)
        self.assertFalse(any("заряд 2" in t for t in texts(fr.advisories(MORTAR, 2, 1000, 0, 300, True))))
        self.assertFalse(any("заряд 2" in t for t in texts(fr.advisories(MORTAR, 1, 1000, 0, 299, True))))
        self.assertFalse(any("заряд 2" in t for t in texts(fr.advisories(SLEDGE, 0, 1000, 0, 500, True))))

    def test_far_dispersion_is_warning(self):
        self.assertEqual(fr.advisories(MORTAR, 2, 4050, None, None, False)[-1][0], "warn")


class NamesTest(unittest.TestCase):
    def test_display_names(self):
        self.assertEqual(fr.display_name(MORTAR), "Молот")
        self.assertEqual(fr.display_name(SLEDGE), "Кувалда")
        self.assertEqual(fr.display_name("Другое"), "Другое")


if __name__ == "__main__":
    unittest.main()
