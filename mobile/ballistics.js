// Расчёт возвышения — точный перенос ballistics.py (программа для ПК).
// Формулы:
//   • возвышение — линейная интерполяция между соседними строками (возвышение, delev, время);
//     на дальности из таблицы это ровно табличное значение;
//   • поправка на превышение — delev MIL на каждые 100 м разницы высот:
//     цель выше орудия → возвышение уменьшается, ниже → увеличивается.
(function (root) {
  "use strict";

  class OutOfTableError extends Error {
    constructor(title, details) {
      super(`${title}. ${details}`);
      this.title = title;
      this.details = details;
    }
  }

  // Как формат {x:g} в Python: 525 → "525", 525.5 → "525.5"
  function g(x) {
    return String(Number(Number(x).toPrecision(6)));
  }

  function chargeTables(data, weapon) {
    return (data[weapon] && data[weapon].charge_data) || {};
  }

  function chargeRows(data, weapon, charge) {
    return chargeTables(data, weapon)[String(charge)] || [];
  }

  function allowedCharges(data, weapon) {
    return Object.keys(chargeTables(data, weapon)).map(Number).sort((a, b) => a - b);
  }

  // [мин. дальность, макс. дальность, шаг таблицы] или null
  function chargeRange(rows) {
    if (!rows.length) return null;
    const step = rows.length > 1 ? rows[1].range - rows[0].range : 0;
    return [rows[0].range, rows[rows.length - 1].range, step];
  }

  function chargesForDistance(data, weapon, distance) {
    return allowedCharges(data, weapon).filter((charge) => {
      const span = chargeRange(chargeRows(data, weapon, charge));
      return span && span[0] <= distance && distance <= span[1];
    });
  }

  // Соседние строки [снизу, сверху] или [null, null], если вне таблицы
  function closestRows(rows, distance) {
    if (!rows.length || distance < rows[0].range || distance > rows[rows.length - 1].range) {
      return [null, null];
    }
    let lo = 0, hi = rows.length - 1;
    while (lo < hi) {                      // Первая строка с range >= distance
      const mid = (lo + hi) >> 1;
      if (rows[mid].range < distance) lo = mid + 1; else hi = mid;
    }
    if (rows[lo].range === distance) return [rows[lo], rows[lo]];
    return [rows[lo - 1], rows[lo]];
  }

  // [elev, delev, time, нижняя строка, верхняя строка] или null.
  // На дальности из таблицы — ровно табличная строка.
  function interpolate(rows, distance) {
    const [lower, upper] = closestRows(rows, distance);
    if (!lower) return null;
    const lerp = (key) => lerpRows(lower, upper, distance, key);
    return [lerp("elev"), lerp("delev"), lerp("time"), lower, upper];
  }

  // Значение столбца между двумя строками таблицы (для одной строки — само значение)
  function lerpRows(lower, upper, distance, key) {
    const span = upper.range - lower.range;
    const ratio = span ? (distance - lower.range) / span : 0;
    return lower[key] + (upper[key] - lower[key]) * ratio;
  }

  // [итоговое возвышение, величина поправки >= 0]
  function heightCorrection(elevation, delev, gunHeight, targetHeight) {
    if (delev === null || delev === undefined) return [elevation, 0];
    const adjustment = Math.abs(gunHeight - targetHeight) * (delev / 100);
    if (targetHeight > gunHeight) return [elevation - adjustment, adjustment];
    return [elevation + adjustment, adjustment];
  }

  // Поправка времени полёта (4-й столбец): цель выше — прилёт раньше, ниже — позже.
  // Знак в методичке не указан — принят по физике навесной стрельбы, как в программе для ПК.
  function flightTimeCorrection(flightTime, timePer100, gunHeight, targetHeight) {
    if (timePer100 === null || timePer100 === undefined) return [flightTime, 0];
    const adjustment = Math.abs(gunHeight - targetHeight) * (timePer100 / 100);
    if (targetHeight > gunHeight) return [flightTime - adjustment, adjustment];
    return [flightTime + adjustment, adjustment];
  }

  // Полный расчёт. Поправки на превышение — если заданы обе высоты (не null).
  // Бросает OutOfTableError, если дальность вне диапазона заряда.
  function solve(data, weapon, charge, distance, gunHeight = null, targetHeight = null) {
    const rows = chargeRows(data, weapon, charge);
    const result = interpolate(rows, distance);
    if (!result) {
      const span = chargeRange(rows);
      const hint = span ? ` Дальность заряда ${span[0]} – ${span[1]} м.` : "";
      throw new OutOfTableError("Вне диапазона", `${g(distance)} м недоступно для заряда ${charge}.${hint}`);
    }
    const [elevation, delev, flightTime, lower, upper] = result;

    if (gunHeight === null || targetHeight === null) {
      return { elevation, baseElevation: elevation, flightTime, correction: null, lowerRow: lower, upperRow: upper,
               baseFlightTime: flightTime, timeCorrection: null };
    }
    const final = heightCorrection(elevation, delev, gunHeight, targetHeight)[0];
    const timePer100 = lerpRows(lower, upper, distance, "time_per_100");
    const correctedTime = flightTimeCorrection(flightTime, timePer100, gunHeight, targetHeight)[0];
    return { elevation: final, baseElevation: elevation, flightTime: correctedTime, correction: final - elevation,
             lowerRow: lower, upperRow: upper, baseFlightTime: flightTime, timeCorrection: correctedTime - flightTime };
  }

  // Расчёт по всем зарядам орудия, которые достают до дистанции: [[заряд, решение], …]
  function compareCharges(data, weapon, distance, gunHeight = null, targetHeight = null) {
    const result = [];
    for (const charge of allowedCharges(data, weapon)) {
      try {
        result.push([charge, solve(data, weapon, charge, distance, gunHeight, targetHeight)]);
      } catch (e) {
        if (!(e instanceof OutOfTableError)) throw e;
      }
    }
    return result;
  }

  // Заряд с самым коротким временем полёта (правило методички) или null
  function fastestCharge(data, weapon, distance) {
    const options = compareCharges(data, weapon, distance);
    if (!options.length) return null;
    return options.reduce((a, b) => (b[1].flightTime < a[1].flightTime ? b : a))[0];
  }

  const MILS_PER_CIRCLE = 6400; // Угломер НАТО, как в Arma 3

  // Корректировка огня относительно линии орудие–цель.
  // along — сдвиг по дальности (+ дальше: был недолёт), lateral — вбок (+ правее).
  // Возвращает [новая дистанция, поправка направления в милах: + вправо, − влево].
  function adjustFire(baseDistance, along, lateral) {
    const forward = baseDistance + along;
    return [Math.hypot(forward, lateral), Math.atan2(lateral, forward) * MILS_PER_CIRCLE / (2 * Math.PI)];
  }

  // Проверка целостности таблиц: список проблем (пустой — всё в порядке)
  function validateWeaponData(data) {
    const problems = [];
    const required = ["range", "elev", "delev", "time_per_100", "time"];
    for (const weapon of Object.keys(data)) {
      for (const [charge, rows] of Object.entries(chargeTables(data, weapon))) {
        const where = `${weapon}, заряд ${charge}`;
        if (!rows.length) { problems.push(`${where}: пустая таблица`); continue; }
        rows.forEach((row, i) => {
          const missing = required.filter((key) => !(key in row));
          if (missing.length) problems.push(`${where}, строка ${i}: нет полей ${missing.join(", ")}`);
        });
        const ranges = rows.map((row) => row.range || 0);
        if (ranges.some((r, i) => i > 0 && r <= ranges[i - 1])) problems.push(`${where}: дальности не возрастают строго`);
      }
    }
    return problems;
  }

  const api = {
    OutOfTableError, g, chargeRows, allowedCharges, chargeRange, chargesForDistance,
    closestRows, interpolate, heightCorrection, solve, validateWeaponData,
    MILS_PER_CIRCLE, adjustFire, compareCharges, fastestCharge, flightTimeCorrection,
  };
  root.Ballistics = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
