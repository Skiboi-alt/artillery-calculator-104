// Расчёт возвышения — точный перенос ballistics.py (программа для ПК).
// Формулы:
//   • табличный режим — точное совпадение дальности со строкой таблицы;
//   • интерполяция — линейная между соседними строками (возвышение, delev, время);
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

  function tableLookup(rows, distance) {
    return rows.find((row) => row.range === distance) || null;
  }

  // [elev, delev, time, нижняя строка, верхняя строка] или null
  function interpolate(rows, distance) {
    const [lower, upper] = closestRows(rows, distance);
    if (!lower) return null;
    const span = upper.range - lower.range;
    const ratio = span ? (distance - lower.range) / span : 0;
    const lerp = (key) => lower[key] + (upper[key] - lower[key]) * ratio;
    return [lerp("elev"), lerp("delev"), lerp("time"), lower, upper];
  }

  // [итоговое возвышение, величина поправки >= 0]
  function heightCorrection(elevation, delev, gunHeight, targetHeight) {
    if (delev === null || delev === undefined) return [elevation, 0];
    const adjustment = Math.abs(gunHeight - targetHeight) * (delev / 100);
    if (targetHeight > gunHeight) return [elevation - adjustment, adjustment];
    return [elevation + adjustment, adjustment];
  }

  // Полный расчёт. mode: "table" | "nontable". Бросает OutOfTableError, если значения нет.
  function solve(data, weapon, charge, distance, mode, gunHeight = 0, targetHeight = 0, applyCorrection = false) {
    const rows = chargeRows(data, weapon, charge);
    let elevation, delev, flightTime, lower, upper;
    if (mode === "table") {
      const row = tableLookup(rows, distance);
      if (!row) {
        throw new OutOfTableError(
          "Нет табличного значения",
          `Для ${g(distance)} м на заряде ${charge} строки в таблице нет — выберите «Интерполяция».`
        );
      }
      [elevation, delev, flightTime, lower, upper] = [row.elev, row.delev, row.time, row, row];
    } else {
      const result = interpolate(rows, distance);
      if (!result) {
        const span = chargeRange(rows);
        const hint = span ? ` Дальность заряда ${span[0]} – ${span[1]} м.` : "";
        throw new OutOfTableError("Вне диапазона", `${g(distance)} м недоступно для заряда ${charge}.${hint}`);
      }
      [elevation, delev, flightTime, lower, upper] = result;
    }

    let final = elevation, correction = null;
    if (applyCorrection) {
      final = heightCorrection(elevation, delev, gunHeight, targetHeight)[0];
      correction = final - elevation;
    }
    return { elevation: final, baseElevation: elevation, flightTime, correction, lowerRow: lower, upperRow: upper };
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
    closestRows, tableLookup, interpolate, heightCorrection, solve, validateWeaponData,
  };
  root.Ballistics = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
