"""Правила из методички «Обучение бойцов специализации AC (для 104-го ДОБ)».

Подсказки к результату и названия орудий как в подразделении.
Чистые функции без интерфейса — проверяются тестами; мобильная версия получает те же
константы через mobile/data.js.
"""

import ballistics

# Названия орудий как в подразделении (ключи таблиц и сохранений не меняются)
DISPLAY_NAMES = {"Миномёт": "Молот", "Кувалда": "Кувалда"}

# «При стрельбе на гору высотой 300+ метров лучше выбирать Charge 2»
HIGH_TARGET_M = 300
HIGH_TARGET_WEAPON = "Миномёт"
HIGH_TARGET_CHARGE = 2
# Разброс Молота до 20 м, особенно на 4000+ м
DISPERSION_M = 20
DISPERSION_FAR_M = 4000


def display_name(weapon):
    return DISPLAY_NAMES.get(weapon, weapon)


def advisories(weapon, charge, distance, gun_height, target_height):
    """Подсказки к результату: [(уровень, текст), …], уровень — "warn" или "info".

    gun_height / target_height — None, если высота не введена (тогда поправки на превышение нет).
    """
    result = []
    if gun_height is None or target_height is None:
        result.append(("info", "Высоты не введены — поправка на превышение не учтена"))
    else:
        diff = target_height - gun_height
        if weapon == HIGH_TARGET_WEAPON and diff >= HIGH_TARGET_M and charge < HIGH_TARGET_CHARGE:
            result.append(("warn", f"Цель выше на {diff:g} м — берите заряд {HIGH_TARGET_CHARGE}: "
                                   f"дуги заряда {charge} может не хватить"))
    far = distance >= DISPERSION_FAR_M
    result.append(("warn" if far else "info",
                   f"Разброс до {DISPERSION_M} м{' (дальняя дистанция)' if far else ''} — "
                   f"проверьте, что союзников нет в радиусе {DISPERSION_M} м"))
    return result


def recommended_charge(weapon_data, weapon, distance, gun_height=None, target_height=None):
    """Заряд для автоподбора: самый быстрый из подходящих, но при цели выше на 300+ м
    для Молота — заряд 2 (дуги меньших зарядов может не хватить). None — ни один не достаёт."""
    if gun_height is not None and target_height is not None and weapon == HIGH_TARGET_WEAPON \
            and target_height - gun_height >= HIGH_TARGET_M \
            and HIGH_TARGET_CHARGE in ballistics.charges_for_distance(weapon_data, weapon, distance):
        return HIGH_TARGET_CHARGE
    return ballistics.fastest_charge(weapon_data, weapon, distance)
