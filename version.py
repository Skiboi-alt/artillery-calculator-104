"""Версия программы и список «Что нового».

При выпуске новой версии:
    1. Поднимите APP_VERSION и добавьте пункты в WHATS_NEW.
    2. python tools/export_mobile.py   (версия попадёт и в мобильную версию)
    3. git tag vX.Y.Z && git push --tags   — GitHub соберёт exe и выложит релиз.
"""

APP_VERSION = "2.1.0"
REPOSITORY = "Skiboi-alt/artillery-calculator-104"
MOBILE_URL = "https://skiboi-alt.github.io/artillery-calculator-104/"

# Новые версии — сверху
WHATS_NEW = {
    "2.1.0": [
        "Корректировка огня: «Недолёт», «Перелёт», «Левее», «Правее» на заданное число метров — "
        "дистанция пересчитывается, поправка направления показывается в милах",
        "Сравнение зарядов: возвышение и время полёта по всем подходящим зарядам, нажатие — выбрать заряд",
        "Таймер полёта: обратный отсчёт до разрыва со звуковым сигналом за 5 секунд и в момент разрыва",
        "Справка по F1 или кнопке «?»",
        "Номер версии и окно «Что нового» после обновления",
        "Программа для ПК сама сообщает о выходе новой версии",
    ],
    "2.0.0": [
        "Новый интерфейс в стиле 104-го батальона «Волчья стая», анимации",
        "Подсказка зарядов, история расчётов, управление с клавиатуры",
        "Мобильная версия для Android и iPhone",
    ],
}


def parse_version(text):
    """'v2.1.0' → (2, 1, 0); нечисловые части считаются нулём"""
    parts = []
    for piece in str(text).strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(candidate, current=APP_VERSION):
    return parse_version(candidate) > parse_version(current)
