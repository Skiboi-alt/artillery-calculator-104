"""Тесты расчёта. Запуск из папки проекта: python -m unittest"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ballistics as b  # noqa: E402
from weapons_data import WEAPON_DATA  # noqa: E402

INDEX = b.build_index(WEAPON_DATA)
MORTAR, SLEDGE = "Миномёт", "Кувалда"


def solve(weapon, charge, distance, mode, gun=0.0, target=0.0, correction=False):
    return b.solve(WEAPON_DATA, INDEX, weapon, charge, distance, mode, gun, target, correction)


class DataIntegrityTest(unittest.TestCase):
    def test_tables_are_valid(self):
        self.assertEqual(b.validate_weapon_data(WEAPON_DATA), [])

    def test_row_count_unchanged(self):
        rows = sum(len(r) for w in WEAPON_DATA.values() for r in w["charge_data"].values())
        self.assertEqual(rows, 520)

    def test_charges(self):
        self.assertEqual(b.allowed_charges(WEAPON_DATA, MORTAR), [0, 1, 2])
        self.assertEqual(b.allowed_charges(WEAPON_DATA, SLEDGE), [0, 1, 2, 3, 4])

    def test_validator_finds_problems(self):
        broken = {"X": {"charge_data": {0: [{"range": 100, "elev": 1}, {"range": 50, "elev": 2}], 1: []}}}
        problems = b.validate_weapon_data(broken)
        self.assertEqual(len(problems), 4)  # 2 строки без полей, порядок дальностей, пустая таблица


class TableModeTest(unittest.TestCase):
    def test_exact_row(self):
        s = solve(MORTAR, 1, 500, "table")
        self.assertEqual((s.elevation, s.flight_time, s.correction), (1471, 28.3, None))

    def test_float_distance_matches_int_key(self):
        self.assertEqual(solve(MORTAR, 1, 500.0, "table").elevation, 1471)

    def test_sledgehammer(self):
        s = solve(SLEDGE, 3, 15000, "table")
        self.assertEqual((s.elevation, s.flight_time), (1418, 130.0))

    def test_missing_row(self):
        with self.assertRaises(b.OutOfTableError) as ctx:
            solve(MORTAR, 1, 525, "table")
        self.assertEqual(ctx.exception.title, "Нет табличного значения")


class InterpolationTest(unittest.TestCase):
    def test_midpoint(self):
        s = solve(MORTAR, 1, 525, "nontable")
        self.assertAlmostEqual(s.elevation, 1464.5)          # между 1471 и 1458
        self.assertAlmostEqual(s.flight_time, 28.3)
        self.assertEqual((s.lower_row["range"], s.upper_row["range"]), (500, 550))

    def test_interpolates_delev_and_time(self):
        elev, delev, time_, lower, upper = b.interpolate(b.charge_rows(WEAPON_DATA, MORTAR, 0), 425)
        self.assertAlmostEqual(elev, (1127 + 1029) / 2)
        self.assertAlmostEqual(delev, (61.0 + 91.0) / 2)
        self.assertAlmostEqual(time_, (12.8 + 12.1) / 2)

    def test_exact_distance_in_interpolation_mode(self):
        s = solve(MORTAR, 1, 500, "nontable")
        self.assertEqual(s.elevation, 1471)
        self.assertIs(s.lower_row, s.upper_row)

    def test_table_edges(self):
        self.assertEqual(solve(MORTAR, 1, 150, "nontable").elevation, 1562)
        self.assertEqual(solve(MORTAR, 1, 1950, "nontable").elevation, 913)

    def test_out_of_range(self):
        for distance in (149.9, 1950.1, 5000):
            with self.assertRaises(b.OutOfTableError):
                solve(MORTAR, 1, distance, "nontable")


class HeightCorrectionTest(unittest.TestCase):
    def test_target_higher_decreases_elevation(self):
        s = solve(MORTAR, 1, 500, "table", gun=0, target=100, correction=True)
        self.assertAlmostEqual(s.elevation, 1471 - 3.2)
        self.assertAlmostEqual(s.correction, -3.2)
        self.assertEqual(s.base_elevation, 1471)

    def test_target_lower_increases_elevation(self):
        s = solve(MORTAR, 1, 525, "nontable", gun=120, target=80, correction=True)
        self.assertAlmostEqual(s.correction, 0.4 * (3.2 + 3.5) / 2)
        self.assertAlmostEqual(s.elevation, 1464.5 + 1.34)

    def test_equal_heights(self):
        self.assertEqual(b.height_correction(1000, 5.0, 50, 50), (1000, 0.0))

    def test_no_delev(self):
        self.assertEqual(b.height_correction(1000, None, 0, 10), (1000, 0.0))

    def test_correction_disabled_ignores_heights(self):
        s = solve(MORTAR, 1, 500, "table", gun=0, target=500, correction=False)
        self.assertEqual((s.elevation, s.correction), (1471, None))


class ChargeHelpersTest(unittest.TestCase):
    def test_charge_range(self):
        self.assertEqual(b.charge_range(b.charge_rows(WEAPON_DATA, MORTAR, 1)), (150, 1950, 50))
        self.assertEqual(b.charge_range(b.charge_rows(WEAPON_DATA, SLEDGE, 2)), (5300, 15400, 100))
        self.assertIsNone(b.charge_range([]))

    def test_charges_for_distance(self):
        self.assertEqual(b.charges_for_distance(WEAPON_DATA, MORTAR, 400), [0, 1, 2])
        self.assertEqual(b.charges_for_distance(WEAPON_DATA, MORTAR, 1000), [1, 2])
        self.assertEqual(b.charges_for_distance(WEAPON_DATA, MORTAR, 3000), [2])
        self.assertEqual(b.charges_for_distance(WEAPON_DATA, MORTAR, 10000), [])
        self.assertEqual(b.charges_for_distance(WEAPON_DATA, SLEDGE, 15000), [2, 3])

    def test_closest_rows_bounds(self):
        rows = b.charge_rows(WEAPON_DATA, MORTAR, 0)
        self.assertEqual(b.closest_rows(rows, 49), (None, None))
        self.assertEqual(b.closest_rows(rows, 451), (None, None))
        self.assertEqual(b.closest_rows([], 100), (None, None))


if __name__ == "__main__":
    unittest.main()
