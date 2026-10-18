"""Описание релиза для GitHub из version.py: python tools/release_notes.py > notes.md"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from version import APP_VERSION, MOBILE_URL, REPOSITORY, WHATS_NEW  # noqa: E402

EXE_NAME = "Artillery-Calculator-104.exe"


def render(version=APP_VERSION):
    items = "\n".join(f"- {item}" for item in WHATS_NEW.get(version, []))
    return f"""## Что нового в {version}

{items}

## Как установить

**Windows:** скачайте `{EXE_NAME}` ниже и запустите — Python не нужен.
Сохранения и настройки появятся рядом с exe. Windows может предупредить о неизвестном издателе
(exe не подписан): «Подробнее» → «Выполнить в любом случае». Программа сама сообщит о следующей версии.

**Телефон (Android и iPhone):** {MOBILE_URL} — откройте и установите на главный экран.
Мобильная версия обновляется сама.

Полный список изменений — [CHANGELOG.md](https://github.com/{REPOSITORY}/blob/main/CHANGELOG.md).
"""


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(render())
