// Правила из методички — точный перенос field_rules.py (константы приходят из data.js).
(function (root) {
  "use strict";
  const R = root.FIELD_RULES;
  const g = (x) => String(Number(Number(x).toPrecision(6)));

  function displayName(weapon) {
    return R.displayNames[weapon] || weapon;
  }

  // Подсказки к результату: [[уровень, текст], …]; высоты — null, если не введены
  function advisories(weapon, charge, distance, gunHeight, targetHeight, correctionOn) {
    const result = [];
    if (gunHeight !== null && targetHeight !== null) {
      const diff = targetHeight - gunHeight;
      if (!correctionOn && Math.abs(diff) >= R.heightRecommended) {
        const required = Math.abs(diff) >= R.heightRequired;
        result.push([required ? "warn" : "info",
          `Перепад высот ${g(Math.abs(diff))} м — поправка на превышение ${required ? "обязательна" : "рекомендуется"}`]);
      }
      if (weapon === R.highTargetWeapon && diff >= R.highTarget && charge < R.highTargetCharge) {
        result.push(["warn", `Цель выше на ${g(diff)} м — берите заряд ${R.highTargetCharge}: дуги заряда ${charge} может не хватить`]);
      }
    }
    const far = distance >= R.dispersionFar;
    result.push([far ? "warn" : "info",
      `Разброс до ${R.dispersion} м${far ? " (дальняя дистанция)" : ""} — проверьте, что союзников нет в радиусе ${R.dispersion} м`]);
    return result;
  }

  const api = { displayName, advisories };
  root.FieldRules = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
