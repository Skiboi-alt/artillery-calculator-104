"""Выгрузить таблицы, палитру и эмблему для мобильной версии (mobile/data.js).

Единственный источник данных — weapons_data.py и ui_widgets.py. После их изменения:
    python tools/export_mobile.py
Тест tests/test_mobile_export.py проверяет, что mobile/data.js не устарел.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ui_widgets import COLORS, wolf_shapes  # noqa: E402
from version import APP_VERSION, REPOSITORY, WHATS_NEW  # noqa: E402
from weapons_data import WEAPON_DATA  # noqa: E402

TARGET = os.path.join(ROOT, "mobile", "data.js")


def render():
    outline, cutouts, left_eye, right_eye = wolf_shapes()
    wolf = {"outline": outline, "cutouts": cutouts, "leftEye": left_eye, "rightEye": right_eye}

    def dump(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    return (
        "// Сгенерировано tools/export_mobile.py из weapons_data.py и ui_widgets.py — не редактировать вручную.\n"
        "(function (root) {\n"
        f"  root.WEAPON_DATA = {dump(WEAPON_DATA)};\n"
        f"  root.THEME_COLORS = {dump(COLORS)};\n"
        f"  root.WOLF_SHAPES = {dump(wolf)};\n"
        f"  root.APP_INFO = {dump({'version': APP_VERSION, 'repository': REPOSITORY, 'whatsNew': WHATS_NEW})};\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : this);\n"
    )


def main():
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        f.write(render())
    print("Готово:", TARGET)


if __name__ == "__main__":
    main()
