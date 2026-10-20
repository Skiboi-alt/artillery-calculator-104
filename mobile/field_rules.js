// Правила из методички — точный перенос field_rules.py (константы приходят из data.js).
(function (root) {
  "use strict";
  const R = root.FIELD_RULES;
  const B = root.Ballistics || (typeof require !== "undefined" ? require("./ballistics.js") : null);
  const g = (x) => String(Number(Number(x).toPrecision(6)));

  function displayName(weapon) {
    return R.displayNames[weapon] || weapon;
  }

  // Подсказки к результату: [[уровень, текст], …]; высоты — null, если не введены (поправки нет)
  function advisories(weapon, charge, distance, gunHeight, targetHeight) {
    const result = [];
    if (gunHeight === null || targetHeight === null) {
      result.push(["info", "Высоты не введены — поправка на превышение не учтена"]);
    } else {
      const diff = targetHeight - gunHeight;
      if (weapon === R.highTargetWeapon && diff >= R.highTarget && charge < R.highTargetCharge) {
        result.push(["warn", `Цель выше на ${g(diff)} м — берите заряд ${R.highTargetCharge}: дуги заряда ${charge} может не хватить`]);
      }
    }
    const far = distance >= R.dispersionFar;
    result.push([far ? "warn" : "info",
      `Разброс до ${R.dispersion} м${far ? " (дальняя дистанция)" : ""} — проверьте, что союзников нет в радиусе ${R.dispersion} м`]);
    return result;
  }

  // Заряд для автоподбора: самый быстрый, но при цели выше на 300+ м для Молота — заряд 2
  function recommendedCharge(data, weapon, distance, gunHeight = null, targetHeight = null) {
    if (gunHeight !== null && targetHeight !== null && weapon === R.highTargetWeapon
        && targetHeight - gunHeight >= R.highTarget
        && B.chargesForDistance(data, weapon, distance).includes(R.highTargetCharge)) {
      return R.highTargetCharge;
    }
    return B.fastestCharge(data, weapon, distance);
  }

  const api = { displayName, advisories, recommendedCharge };
  root.FieldRules = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
