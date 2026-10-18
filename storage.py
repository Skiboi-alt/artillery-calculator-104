"""Файлы программы: сохранения, настройки, лог.

Все файлы лежат рядом с exe (или рядом со скриптом при запуске из исходников):
    saves.json     — именованные сохранения
    settings.json  — последнее орудие/заряд/режим, положение окна, история расчётов
    calculator.log — журнал ошибок (в собранном exe нет консоли, print не виден)
"""

import json
import logging
import os
import sys
import tempfile
from logging.handlers import RotatingFileHandler

log = logging.getLogger("calculator")


def get_app_dir():
    """Папка приложения: рядом с exe (PyInstaller) или рядом со скриптом.

    В onefile-сборке __file__ указывает во временную папку, которая удаляется
    после закрытия программы, поэтому сохранения пропадали бы.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(name):
    """Путь к ресурсу, вшитому в exe (или лежащему рядом со скриптом)"""
    base = getattr(sys, "_MEIPASS", get_app_dir())
    return os.path.join(base, name)


def setup_logging(directory=None):
    """Журнал в calculator.log (до ~256 КБ, плюс одна старая копия)"""
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    path = os.path.join(directory or get_app_dir(), "calculator.log")
    try:
        handler = RotatingFileHandler(path, maxBytes=256 * 1024, backupCount=1, encoding="utf-8")
    except OSError:
        handler = logging.StreamHandler()  # Папка только для чтения — пишем хотя бы в консоль
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    return log


def atomic_write_json(path, data):
    """Записать JSON без риска испортить файл: временный файл + атомарная замена.

    Если программа упадёт во время записи, старый файл останется целым.
    """
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def read_json_dict(path):
    """Прочитать JSON-объект. Возвращает {} если файла нет или он повреждён (с записью в лог)"""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        log.warning("Файл %s повреждён — используются пустые значения", path)
        _keep_broken_copy(path)
        return {}
    except OSError as e:
        log.error("Не удалось прочитать %s: %s", path, e)
        return {}
    if not isinstance(data, dict):
        log.warning("Неверный формат %s — ожидался JSON-объект", path)
        return {}
    return data


def _keep_broken_copy(path):
    """Сохранить повреждённый файл как .broken, чтобы данные можно было восстановить вручную"""
    try:
        os.replace(path, path + ".broken")
    except OSError:
        pass


class Store:
    """Сохранения и настройки программы"""

    def __init__(self, directory=None):
        self.directory = directory or get_app_dir()
        self.saves_path = os.path.join(self.directory, "saves.json")
        self.settings_path = os.path.join(self.directory, "settings.json")
        # Отбрасываем записи неверного формата, чтобы не падать при загрузке
        self.saves = {str(k): v for k, v in read_json_dict(self.saves_path).items() if isinstance(v, dict)}
        self.settings = read_json_dict(self.settings_path)

    def write_saves(self):
        """True при успехе"""
        try:
            atomic_write_json(self.saves_path, self.saves)
            return True
        except OSError as e:
            log.error("Не удалось записать сохранения: %s", e)
            return False

    def write_settings(self):
        try:
            atomic_write_json(self.settings_path, self.settings)
            return True
        except OSError as e:
            log.error("Не удалось записать настройки: %s", e)
            return False
