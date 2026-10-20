"""Расчёт возвышения по баллистическим таблицам.

Чистые функции без интерфейса — их проверяют тесты в папке tests/.
Формулы:
    • возвышение — линейная интерполяция между соседними строками таблицы (возвышение, delev, время);
      на дальности из таблицы это ровно табличное значение;
    • поправка на превышение — delev MIL на каждые 100 м разницы высот:
      цель выше орудия → возвышение уменьшается, ниже → увеличивается;
    • поправка времени полёта — time_per_100 с на каждые 100 м разницы высот (4-й столбец таблицы):
      цель выше → снаряд встречает её раньше на нисходящей ветви, время меньше; ниже — больше.
      Знак в методичке не указан — принят по физике навесной стрельбы.
    Поправки применяются, когда известны обе высоты — орудия и цели.
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
    flight_time: float               # Время полёта (с поправкой на превышение, если она есть), с
    correction: Optional[float]      # Поправка, MIL (None — высоты не заданы, поправки нет)
    lower_row: dict                  # Строка таблицы снизу (на табличной дальности = upper_row)
    upper_row: dict                  # Строка таблицы сверху
    base_flight_time: Optional[float] = None   # Время полёта по таблице, без поправки
    time_correction: Optional[float] = None    # Поправка времени, с (None — поправки нет)


class OutOfTableError(ValueError):
    """Дальность вне диапазона заряда"""

    def __init__(self, title, details):
        super().__init__(f"{title}. {details}")
        self.title = title
        self.details = details


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


def interpolate(rows, distance):
    """Линейная интерполяция (elev, delev, time, нижняя строка, верхняя строка) или None"""
    lower, upper = closest_rows(rows, distance)
    if lower is None:
        return None
    return (_lerp_rows(lower, upper, distance, "elev"), _lerp_rows(lower, upper, distance, "delev"),
            _lerp_rows(lower, upper, distance, "time"), lower, upper)


def _lerp_rows(lower, upper, distance, key):
    """Значение столбца key между двумя строками таблицы (для одной строки — само значение)"""
    span = upper["range"] - lower["range"]
    ratio = (distance - lower["range"]) / span if span else 0.0
    return lower[key] + (upper[key] - lower[key]) * ratio


def height_correction(elevation, delev, gun_height, target_height):
    """(итоговое возвышение, величина поправки ≥ 0) с учётом разницы высот"""
    if delev is None:
        return elevation, 0.0
    adjustment = abs(gun_height - target_height) * (delev / 100)
    if target_height > gun_height:
        return elevation - adjustment, adjustment
    return elevation + adjustment, adjustment


def flight_time_correction(flight_time, time_per_100, gun_height, target_height):
    """(итоговое время, величина поправки ≥ 0): time_per_100 с на каждые 100 м разницы высот"""
    if time_per_100 is None:
        return flight_time, 0.0
    adjustment = abs(gun_height - target_height) * (time_per_100 / 100)
    if target_height > gun_height:
        return flight_time - adjustment, adjustment
    return flight_time + adjustment, adjustment


def solve(weapon_data, weapon, charge, distance, gun_height=None, target_height=None):
    """Полный расчёт. Поправки на превышение — если заданы обе высоты.

    Бросает OutOfTableError, если дальность вне диапазона заряда.
    """
    rows = charge_rows(weapon_data, weapon, charge)
    result = interpolate(rows, distance)
    if result is None:
        span = charge_range(rows)
        hint = f" Дальность заряда {span[0]} – {span[1]} м." if span else ""
        raise OutOfTableError("Вне диапазона", f"{distance:g} м недоступно для заряда {charge}.{hint}")
    elevation, delev, flight_time, lower, upper = result

    if gun_height is None or target_height is None:
        return Solution(elevation, elevation, flight_time, None, lower, upper, flight_time, None)

    final, _ = height_correction(elevation, delev, gun_height, target_height)
    time_per_100 = _lerp_rows(lower, upper, distance, "time_per_100")
    corrected_time, _ = flight_time_correction(flight_time, time_per_100, gun_height, target_height)
    return Solution(final, elevation, corrected_time, final - elevation, lower, upper,
                    flight_time, corrected_time - flight_time)


def compare_charges(weapon_data, weapon, distance, gun_height=None, target_height=None):
    """Расчёт по всем зарядам орудия, которые достают до дистанции: [(заряд, Solution), …]"""
    result = []
    for charge in allowed_charges(weapon_data, weapon):
        try:
            result.append((charge, solve(weapon_data, weapon, charge, distance, gun_height, target_height)))
        except OutOfTableError:
            pass
    return result


def fastest_charge(weapon_data, weapon, distance):
    """Заряд с самым коротким временем полёта (правило методички) или None, если ни один не достаёт"""
    options = compare_charges(weapon_data, weapon, distance)
    if not options:
        return None
    return min(options, key=lambda item: item[1].flight_time)[0]


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
