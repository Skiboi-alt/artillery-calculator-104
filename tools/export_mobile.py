"""Выгрузить таблицы, палитру и эмблему для мобильной версии (mobile/data.js).

Единственный источник данных — weapons_data.py, themes.py, field_rules.py и version.py. После их изменения:
    python tools/export_mobile.py
Тест tests/test_mobile_export.py проверяет, что mobile/data.js не устарел.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import field_rules as fr  # noqa: E402
import themes  # noqa: E402
from version import APP_VERSION, REPOSITORY, WHATS_NEW  # noqa: E402
from weapons_data import WEAPON_DATA  # noqa: E402

TARGET = os.path.join(ROOT, "mobile", "data.js")


def render():
    units = {
        key: {
            "name": t["name"], "short": t["short"], "of": t["of"], "title": t["title"],
            "watermark": t["watermark"], "colors": t["colors"],
            "emblem": [[role, points] for role, points in t["emblem"]],
        }
        for key, t in themes.THEMES.items()
    }
    theme_info = {"default": themes.DEFAULT_THEME, "order": themes.THEME_ORDER, "units": units}

    def dump(value):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    rules = {
        "displayNames": fr.DISPLAY_NAMES,
        "highTarget": fr.HIGH_TARGET_M, "highTargetWeapon": fr.HIGH_TARGET_WEAPON,
        "highTargetCharge": fr.HIGH_TARGET_CHARGE,
        "dispersion": fr.DISPERSION_M, "dispersionFar": fr.DISPERSION_FAR_M,
    }

    return (
        "// Сгенерировано tools/export_mobile.py из weapons_data.py, themes.py и др. — не редактировать вручную.\n"
        "(function (root) {\n"
        f"  root.WEAPON_DATA = {dump(WEAPON_DATA)};\n"
        f"  root.THEMES = {dump(theme_info)};\n"
        f"  root.APP_INFO = {dump({'version': APP_VERSION, 'repository': REPOSITORY, 'whatsNew': WHATS_NEW})};\n"
        f"  root.FIELD_RULES = {dump(rules)};\n"
        "})(typeof globalThis !== \"undefined\" ? globalThis : this);\n"
    )


def main():
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        f.write(render())
    print("Готово:", TARGET)


if __name__ == "__main__":
    main()
