"""Расчёт возвышения по баллистическим таблицам.

Чистые функции без интерфейса — их проверяют тесты в папке tests/.
Формулы:
    • табличный режим — точное совпадение дальности со строкой таблицы;
    • интерполяция — линейная между соседними строками (возвышение, delev, время);
    • поправка на превышение — delev MIL на каждые 100 м разницы высот:
      цель выше орудия → возвышение уменьшается, ниже → увеличивается.
"""

import math
from bisect import bisect_left
from dataclasses import dataclass
from typing import Optional

MILS_PER_CIRCLE = 6400  # Угломер НАТО, как в Arma 3


@dataclass
class Solution:
    """Результат расчёта"""
    elevation: float                 # Итоговое возвышение, MIL
    base_elevation: float            # Возвышение без поправки на превышение, MIL
    flight_time: float               # Время полёта, с
    correction: Optional[float]      # Поправка, MIL (None — поправка выключена)
    lower_row: dict                  # Строка таблицы снизу (в табличном режиме = upper_row)
    upper_row: dict                  # Строка таблицы сверху


class OutOfTableError(ValueError):
    """Для дальности нет значения: нет строки в таблице или дальность вне диапазона заряда"""

    def __init__(self, title, details):
        super().__init__(f"{title}. {details}")
        self.title = title
        self.details = details


def build_index(weapon_data):
    """Индекс {орудие: {заряд: {дальность: строка}}} для быстрого табличного поиска"""
    return {
        weapon: {charge: {row["range"]: row for row in rows} for charge, rows in info["charge_data"].items()}
        for weapon, info in weapon_data.items()
    }


def charge_rows(weapon_data, weapon, charge):
    """Строки таблицы для орудия и заряда (пустой список, если нет)"""
    return weapon_data.get(weapon, {}).get("charge_data", {}).get(charge, [])


def allowed_charges(weapon_data, weapon):
    return sorted(weapon_data.get(weapon, {}).get("charge_data", {}).keys())


def charge_range(rows):
    """(мин. дальность, макс. дальность, шаг таблицы) или None для пустой таблицы"""
    if not rows:
        return None
    step = rows[1]["range"] - rows[0]["range"] if len(rows) > 1 else 0
    return rows[0]["range"], rows[-1]["range"], step


def charges_for_distance(weapon_data, weapon, distance):
    """Заряды, в диапазон которых попадает дистанция"""
    result = []
    for charge in allowed_charges(weapon_data, weapon):
        span = charge_range(charge_rows(weapon_data, weapon, charge))
        if span and span[0] <= distance <= span[1]:
            result.append(charge)
    return result


def closest_rows(rows, distance):
    """Соседние строки (снизу, сверху) для дальности или (None, None), если вне таблицы"""
    if not rows or distance < rows[0]["range"] or distance > rows[-1]["range"]:
        return None, None
    ranges = [row["range"] for row in rows]
    i = bisect_left(ranges, distance)
    if ranges[i] == distance:
        return rows[i], rows[i]
    return rows[i - 1], rows[i]


def table_lookup(index, weapon, charge, distance):
    """Строка таблицы с точно такой дальностью или None"""
    return index.get(weapon, {}).get(charge, {}).get(distance)


def interpolate(rows, distance):
    """Линейная интерполяция (elev, delev, time, нижняя строка, верхняя строка) или None"""
    lower, upper = closest_rows(rows, distance)
    if lower is None:
        return None
    span = upper["range"] - lower["range"]
    ratio = (distance - lower["range"]) / span if span else 0.0

    def lerp(key):
        return lower[key] + (upper[key] - lower[key]) * ratio

    return lerp("elev"), lerp("delev"), lerp("time"), lower, upper


def height_correction(elevation, delev, gun_height, target_height):
    """(итоговое возвышение, величина поправки ≥ 0) с учётом разницы высот"""
    if delev is None:
        return elevation, 0.0
    adjustment = abs(gun_height - target_height) * (delev / 100)
    if target_height > gun_height:
        return elevation - adjustment, adjustment
    return elevation + adjustment, adjustment


def solve(weapon_data, index, weapon, charge, distance, mode, gun_height=0.0, target_height=0.0,
          apply_correction=False):
    """Полный расчёт. mode: "table" или "nontable". Бросает OutOfTableError, если значения нет."""
    rows = charge_rows(weapon_data, weapon, charge)
    if mode == "table":
        row = table_lookup(index, weapon, charge, distance)
        if row is None:
            raise OutOfTableError(
                "Нет табличного значения",
                f"Для {distance:g} м на заряде {charge} строки в таблице нет — выберите «Интерполяция».",
            )
        elevation, delev, flight_time, lower, upper = row["elev"], row["delev"], row["time"], row, row
    else:
        result = interpolate(rows, distance)
        if result is None:
            span = charge_range(rows)
            hint = f" Дальность заряда {span[0]} – {span[1]} м." if span else ""
            raise OutOfTableError("Вне диапазона", f"{distance:g} м недоступно для заряда {charge}.{hint}")
        elevation, delev, flight_time, lower, upper = result

    if apply_correction:
        final, _ = height_correction(elevation, delev, gun_height, target_height)
        correction = final - elevation
    else:
        final, correction = elevation, None
    return Solution(final, elevation, flight_time, correction, lower, upper)


def adjust_fire(base_distance, along, lateral):
    """Корректировка огня относительно линии орудие–цель.

    along   — сдвиг по дальности, м (+ дальше: был недолёт; − ближе: был перелёт)
    lateral — боковой сдвиг, м (+ правее, − левее)
    Возвращает (новая дистанция, поправка направления в милах: + вправо, − влево).
    """
    forward = base_distance + along
    distance = math.hypot(forward, lateral)
    direction = math.atan2(lateral, forward) * MILS_PER_CIRCLE / (2 * math.pi)
    return distance, direction


def compare_charges(weapon_data, index, weapon, distance, mode, gun_height=0.0, target_height=0.0,
                    apply_correction=False):
    """Расчёт по всем зарядам орудия, которые дают решение: [(заряд, Solution), …]"""
    result = []
    for charge in allowed_charges(weapon_data, weapon):
        try:
            result.append((charge, solve(weapon_data, index, weapon, charge, distance, mode,
                                         gun_height, target_height, apply_correction)))
        except OutOfTableError:
            pass
    return result


def validate_weapon_data(weapon_data):
    """Проверка целостности таблиц. Возвращает список найденных проблем (пустой — всё в порядке)"""
    problems = []
    required = ("range", "elev", "delev", "time_per_100", "time")
    for weapon, info in weapon_data.items():
        for charge, rows in info.get("charge_data", {}).items():
            where = f"{weapon}, заряд {charge}"
            if not rows:
                problems.append(f"{where}: пустая таблица")
                continue
            for i, row in enumerate(rows):
                missing = [key for key in required if key not in row]
                if missing:
                    problems.append(f"{where}, строка {i}: нет полей {', '.join(missing)}")
            ranges = [row.get("range", 0) for row in rows]
            if any(b <= a for a, b in zip(ranges, ranges[1:])):
                problems.append(f"{where}: дальности не возрастают строго")
    return problems
