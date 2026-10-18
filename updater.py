"""Проверка новой версии на GitHub (последний релиз репозитория)"""

import json
import urllib.error
import urllib.request

from version import APP_VERSION, REPOSITORY, is_newer

API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
TIMEOUT = 5


def fetch_latest_release(timeout=TIMEOUT):
    """(тег, ссылка на страницу релиза) или None, если нет сети или релизов"""
    request = urllib.request.Request(API_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"artillery-calculator-104/{APP_VERSION}",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    tag, url = data.get("tag_name"), data.get("html_url")
    return (tag, url) if tag and url else None


def check_for_update(fetch=fetch_latest_release):
    """(тег, ссылка) если на GitHub есть версия новее текущей, иначе None"""
    latest = fetch()
    if latest and is_newer(latest[0]):
        return latest
    return None
