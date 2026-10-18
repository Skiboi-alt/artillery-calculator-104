"""Мобильная версия должна использовать те же таблицы, что и программа для ПК"""

import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import export_mobile  # noqa: E402
from weapons_data import WEAPON_DATA  # noqa: E402


class MobileExportTest(unittest.TestCase):
    def test_data_js_is_up_to_date(self):
        with open(export_mobile.TARGET, encoding="utf-8") as f:
            actual = f.read()
        self.assertEqual(actual, export_mobile.render(),
                         "mobile/data.js устарел — запустите: python tools/export_mobile.py")

    def test_tables_identical(self):
        with open(export_mobile.TARGET, encoding="utf-8") as f:
            match = re.search(r"root\.WEAPON_DATA = (.*?);\n", f.read())
        exported = json.loads(match.group(1))
        # В JSON ключи зарядов — строки
        expected = {w: {"charge_data": {str(c): rows for c, rows in info["charge_data"].items()}}
                    for w, info in WEAPON_DATA.items()}
        self.assertEqual(exported, expected)


if __name__ == "__main__":
    unittest.main()
