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
    def test_only_dispersion_with_heights(self):
        items = fr.advisories(MORTAR, 1, 1000, 100, 120)
        self.assertEqual(len(items), 1)
        self.assertIn("Разброс до 20 м", items[0][1])
        self.assertEqual(items[0][0], "info")

    def test_no_heights_reminder(self):
        items = fr.advisories(MORTAR, 1, 1000, None, None)
        self.assertEqual(items[0], ("info", "Высоты не введены — поправка на превышение не учтена"))
        self.assertEqual(len(items), 2)

    def test_high_target_needs_charge_2(self):
        warn = [t for t in texts(fr.advisories(MORTAR, 1, 1000, 0, 300)) if "заряд 2" in t]
        self.assertEqual(len(warn), 1)
        self.assertFalse(any("заряд 2" in t for t in texts(fr.advisories(MORTAR, 2, 1000, 0, 300))))
        self.assertFalse(any("заряд 2" in t for t in texts(fr.advisories(MORTAR, 1, 1000, 0, 299))))
        self.assertFalse(any("заряд 2" in t for t in texts(fr.advisories(SLEDGE, 0, 1000, 0, 500))))

    def test_far_dispersion_is_warning(self):
        self.assertEqual(fr.advisories(MORTAR, 2, 4050, None, None)[-1][0], "warn")


class RecommendedChargeTest(unittest.TestCase):
    def setUp(self):
        from weapons_data import WEAPON_DATA
        self.data = WEAPON_DATA

    def test_fastest_without_heights(self):
        self.assertEqual(fr.recommended_charge(self.data, MORTAR, 525), 1)
        self.assertEqual(fr.recommended_charge(self.data, MORTAR, 400, 0, 100), 0)

    def test_high_target_prefers_charge_2(self):
        self.assertEqual(fr.recommended_charge(self.data, MORTAR, 525, 0, 340), 2)
        self.assertEqual(fr.recommended_charge(self.data, MORTAR, 525, 0, 299), 1)

    def test_high_target_when_charge_2_does_not_reach(self):
        # 200 м: заряд 2 начинается с 300 м — остаётся самый быстрый из подходящих
        self.assertEqual(fr.recommended_charge(self.data, MORTAR, 200, 0, 400), 0)

    def test_sledgehammer_rule_not_applied(self):
        self.assertEqual(fr.recommended_charge(self.data, SLEDGE, 15000, 0, 500), 2)

    def test_out_of_range(self):
        self.assertIsNone(fr.recommended_charge(self.data, MORTAR, 10000))


class NamesTest(unittest.TestCase):
    def test_display_names(self):
        self.assertEqual(fr.display_name(MORTAR), "Молот")
        self.assertEqual(fr.display_name(SLEDGE), "Кувалда")
        self.assertEqual(fr.display_name("Другое"), "Другое")


if __name__ == "__main__":
    unittest.main()
