"""Правила из методички «Обучение бойцов специализации AC (для 104-го ДОБ)».

Подсказки к результату и названия орудий как в подразделении.
Чистые функции без интерфейса — проверяются тестами; мобильная версия получает те же
константы через mobile/data.js.
"""

# Названия орудий как в подразделении (ключи таблиц и сохранений не меняются)
DISPLAY_NAMES = {"Миномёт": "Молот", "Кувалда": "Кувалда"}

# Поправка на превышение: «рекомендуется от 50 м, обязательно от 100 м»
HEIGHT_RECOMMENDED_M = 50
HEIGHT_REQUIRED_M = 100
# «При стрельбе на гору высотой 300+ метров лучше выбирать Charge 2»
HIGH_TARGET_M = 300
HIGH_TARGET_WEAPON = "Миномёт"
HIGH_TARGET_CHARGE = 2
# Разброс Молота до 20 м, особенно на 4000+ м
DISPERSION_M = 20
DISPERSION_FAR_M = 4000


def display_name(weapon):
    return DISPLAY_NAMES.get(weapon, weapon)


def advisories(weapon, charge, distance, gun_height, target_height, correction_on):
    """Подсказки к результату: [(уровень, текст), …], уровень — "warn" или "info".

    gun_height / target_height — None, если высота не введена.
    """
    result = []
    heights_known = gun_height is not None and target_height is not None
    if heights_known:
        diff = target_height - gun_height
        if not correction_on and abs(diff) >= HEIGHT_RECOMMENDED_M:
            level = "warn" if abs(diff) >= HEIGHT_REQUIRED_M else "info"
            need = "обязательна" if abs(diff) >= HEIGHT_REQUIRED_M else "рекомендуется"
            result.append((level, f"Перепад высот {abs(diff):g} м — поправка на превышение {need}"))
        if weapon == HIGH_TARGET_WEAPON and diff >= HIGH_TARGET_M and charge < HIGH_TARGET_CHARGE:
            result.append(("warn", f"Цель выше на {diff:g} м — берите заряд {HIGH_TARGET_CHARGE}: "
                                   f"дуги заряда {charge} может не хватить"))
    far = distance >= DISPERSION_FAR_M
    result.append(("warn" if far else "info",
                   f"Разброс до {DISPERSION_M} м{' (дальняя дистанция)' if far else ''} — "
                   f"проверьте, что союзников нет в радиусе {DISPERSION_M} м"))
    return result
