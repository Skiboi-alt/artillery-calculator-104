"""Тесты номера версии и проверки обновлений (без обращения к сети)"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import updater  # noqa: E402
import version  # noqa: E402


class VersionTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(version.parse_version("v2.1.0"), (2, 1, 0))
        self.assertEqual(version.parse_version("2.1"), (2, 1, 0))
        self.assertEqual(version.parse_version("v3.0.0-beta"), (3, 0, 0))
        self.assertEqual(version.parse_version("мусор"), (0, 0, 0))

    def test_is_newer(self):
        self.assertTrue(version.is_newer("v2.1.1", "2.1.0"))
        self.assertTrue(version.is_newer("v2.10.0", "2.9.0"))   # Числа, а не строки
        self.assertFalse(version.is_newer("v2.1.0", "2.1.0"))
        self.assertFalse(version.is_newer("v2.0.0", "2.1.0"))

    def test_whats_new_has_current_version(self):
        self.assertIn(version.APP_VERSION, version.WHATS_NEW)
        self.assertEqual(next(iter(version.WHATS_NEW)), version.APP_VERSION)  # Текущая — первой


class UpdaterTest(unittest.TestCase):
    def test_newer_release_found(self):
        fake = lambda: ("v99.0.0", "https://example/release")
        self.assertEqual(updater.check_for_update(fake), ("v99.0.0", "https://example/release"))

    def test_same_or_older_release(self):
        self.assertIsNone(updater.check_for_update(lambda: (f"v{version.APP_VERSION}", "u")))
        self.assertIsNone(updater.check_for_update(lambda: ("v1.0.0", "u")))

    def test_no_network(self):
        self.assertIsNone(updater.check_for_update(lambda: None))


if __name__ == "__main__":
    unittest.main()
