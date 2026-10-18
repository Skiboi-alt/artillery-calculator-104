"""Тесты файлов сохранений и настроек"""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import storage  # noqa: E402


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name):
        return os.path.join(self.dir, name)

    def test_roundtrip_unicode(self):
        store = storage.Store(self.dir)
        store.saves["Высота 212"] = {"weapon": "Миномёт", "distance": "525"}
        self.assertTrue(store.write_saves())
        self.assertEqual(storage.Store(self.dir).saves, store.saves)

    def test_missing_files(self):
        store = storage.Store(self.dir)
        self.assertEqual((store.saves, store.settings), ({}, {}))

    def test_corrupted_file_is_kept_as_broken(self):
        with open(self.path("saves.json"), "w", encoding="utf-8") as f:
            f.write("{ не json")
        self.assertEqual(storage.Store(self.dir).saves, {})
        self.assertTrue(os.path.exists(self.path("saves.json.broken")))

    def test_invalid_entries_dropped(self):
        with open(self.path("saves.json"), "w", encoding="utf-8") as f:
            json.dump({"ok": {"distance": "1"}, "bad": 5}, f)
        self.assertEqual(list(storage.Store(self.dir).saves), ["ok"])

    def test_non_object_json(self):
        with open(self.path("settings.json"), "w", encoding="utf-8") as f:
            json.dump([1, 2], f)
        self.assertEqual(storage.Store(self.dir).settings, {})

    def test_failed_write_keeps_old_file(self):
        target = self.path("saves.json")
        storage.atomic_write_json(target, {"old": {"a": 1}})
        with mock.patch("storage.json.dump", side_effect=OSError("диск полон")):
            with self.assertRaises(OSError):
                storage.atomic_write_json(target, {"new": {}})
        with open(target, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"old": {"a": 1}})
        leftovers = [n for n in os.listdir(self.dir) if n.startswith(".tmp_")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
