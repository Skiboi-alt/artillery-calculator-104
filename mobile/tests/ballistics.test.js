// Тесты расчёта мобильной версии — те же случаи, что в tests/test_ballistics.py.
// Запуск: node mobile/tests/ballistics.test.js  или откройте mobile/tests.html в браузере.
(function (root) {
  "use strict";
  const isNode = typeof module !== "undefined" && module.exports;
  if (isNode) {
    require("../data.js");
    require("../ballistics.js");
    require("../field_rules.js");
  }
  const B = root.Ballistics;
  const F = root.FieldRules;
  const D = root.WEAPON_DATA;
  const MORTAR = "Миномёт", SLEDGE = "Кувалда";
  const solve = (w, c, d, gun = null, target = null) => B.solve(D, w, c, d, gun, target);

  const results = [];
  function test(name, fn) {
    try { fn(); results.push({ name, ok: true }); }
    catch (e) { results.push({ name, ok: false, error: e.message }); }
  }
  function eq(actual, expected) {
    const a = JSON.stringify(actual), b = JSON.stringify(expected);
    if (a !== b) throw new Error(`ожидалось ${b}, получено ${a}`);
  }
  function near(actual, expected, eps = 1e-7) {
    if (Math.abs(actual - expected) > eps) throw new Error(`ожидалось ≈${expected}, получено ${actual}`);
  }
  function throwsOut(fn, title) {
    try { fn(); } catch (e) {
      if (!(e instanceof B.OutOfTableError)) throw e;
      if (title && e.title !== title) throw new Error(`заголовок «${e.title}» вместо «${title}»`);
      return;
    }
    throw new Error("ожидалась ошибка OutOfTableError");
  }

  // Целостность данных
  test("таблицы без ошибок", () => eq(B.validateWeaponData(D), []));
  test("520 строк", () => {
    let n = 0;
    for (const w of Object.values(D)) for (const rows of Object.values(w.charge_data)) n += rows.length;
    eq(n, 520);
  });
  test("заряды орудий", () => {
    eq(B.allowedCharges(D, MORTAR), [0, 1, 2]);
    eq(B.allowedCharges(D, SLEDGE), [0, 1, 2, 3, 4]);
  });
  test("валидатор находит проблемы", () => {
    const broken = { X: { charge_data: { 0: [{ range: 100, elev: 1 }, { range: 50, elev: 2 }], 1: [] } } };
    eq(B.validateWeaponData(broken).length, 4);
  });

  // Табличный режим
  test("точная строка", () => {
    const s = solve(MORTAR, 1, 500);
    eq([s.elevation, s.flightTime, s.correction], [1471, 28.3, null]);
  });
  test("дробная запись дистанции", () => eq(solve(MORTAR, 1, 500.0).elevation, 1471));
  test("Кувалда", () => {
    const s = solve(SLEDGE, 3, 15000);
    eq([s.elevation, s.flightTime], [1418, 130.0]);
  });
  test("вне диапазона — заголовок", () => throwsOut(() => solve(MORTAR, 1, 5000), "Вне диапазона"));

  // Интерполяция
  test("середина между строками", () => {
    const s = solve(MORTAR, 1, 525);
    near(s.elevation, 1464.5);
    near(s.flightTime, 28.3);
    eq([s.lowerRow.range, s.upperRow.range], [500, 550]);
  });
  test("интерполяция delev и времени", () => {
    const [elev, delev, time] = B.interpolate(B.chargeRows(D, MORTAR, 0), 425);
    near(elev, (1127 + 1029) / 2);
    near(delev, (61.0 + 91.0) / 2);
    near(time, (12.8 + 12.1) / 2);
  });
  test("точная дальность в режиме интерполяции", () => {
    const s = solve(MORTAR, 1, 500);
    eq(s.elevation, 1471);
    if (s.lowerRow !== s.upperRow) throw new Error("строки должны совпадать");
  });
  test("края таблицы", () => {
    eq(solve(MORTAR, 1, 150).elevation, 1562);
    eq(solve(MORTAR, 1, 1950).elevation, 913);
  });
  test("вне диапазона", () => {
    for (const d of [149.9, 1950.1, 5000]) throwsOut(() => solve(MORTAR, 1, d), "Вне диапазона");
  });

  // Поправка на превышение
  test("цель выше — возвышение меньше", () => {
    const s = solve(MORTAR, 1, 500, 0, 100);
    near(s.elevation, 1471 - 3.2);
    near(s.correction, -3.2);
    eq(s.baseElevation, 1471);
  });
  test("цель ниже — возвышение больше", () => {
    const s = solve(MORTAR, 1, 525, 120, 80);
    near(s.correction, 0.4 * (3.2 + 3.5) / 2);
    near(s.elevation, 1464.5 + 1.34);
  });
  test("равные высоты", () => eq(B.heightCorrection(1000, 5.0, 50, 50), [1000, 0]));
  test("нет delev", () => eq(B.heightCorrection(1000, null, 0, 10), [1000, 0]));
  test("поправка выключена", () => {
    const s = solve(MORTAR, 1, 500);
    eq([s.elevation, s.correction], [1471, null]);
  });

  // Подбор зарядов
  test("дальность заряда", () => {
    eq(B.chargeRange(B.chargeRows(D, MORTAR, 1)), [150, 1950, 50]);
    eq(B.chargeRange(B.chargeRows(D, SLEDGE, 2)), [5300, 15400, 100]);
    eq(B.chargeRange([]), null);
  });
  test("подходящие заряды", () => {
    eq(B.chargesForDistance(D, MORTAR, 400), [0, 1, 2]);
    eq(B.chargesForDistance(D, MORTAR, 1000), [1, 2]);
    eq(B.chargesForDistance(D, MORTAR, 3000), [2]);
    eq(B.chargesForDistance(D, MORTAR, 10000), []);
    eq(B.chargesForDistance(D, SLEDGE, 15000), [2, 3]);
  });
  test("границы поиска строк", () => {
    const rows = B.chargeRows(D, MORTAR, 0);
    eq(B.closestRows(rows, 49), [null, null]);
    eq(B.closestRows(rows, 451), [null, null]);
    eq(B.closestRows([], 100), [null, null]);
  });
  test("формат как в Python", () => eq([B.g(525), B.g(525.5), B.g(15000)], ["525", "525.5", "15000"]));

  // Корректировка огня
  test("корректировка по дальности", () => {
    eq(B.adjustFire(1000, 50, 0), [1050, 0]);
    eq(B.adjustFire(1000, -100, 0), [900, 0]);
  });
  test("боковая корректировка", () => {
    const [d, dir] = B.adjustFire(1000, 0, 100);
    near(d, 1004.987562, 1e-5);
    near(dir, 101.52, 0.005);
    near(B.adjustFire(1000, 0, -100)[1], -101.52, 0.005);
  });
  test("45° = 800 мил", () => near(B.adjustFire(500, 0, 500)[1], 800));

  // Сравнение зарядов
  test("все подходящие заряды", () => {
    const r = B.compareCharges(D, MORTAR, 400);
    eq(r.map(([c]) => c), [0, 1, 2]);
    eq(r.map(([, s]) => s.elevation), [1127, 1497, 1550]);
  });
  test("между строками — заряды 1 и 2", () => {
    eq(B.compareCharges(D, MORTAR, 525).map(([c]) => c), [1, 2]);
    eq(B.compareCharges(D, MORTAR, 10000), []);
  });
  test("самый быстрый заряд", () => {
    eq([B.fastestCharge(D, MORTAR, 400), B.fastestCharge(D, MORTAR, 1000), B.fastestCharge(D, MORTAR, 3000)], [0, 1, 2]);
    eq([B.fastestCharge(D, SLEDGE, 15000), B.fastestCharge(D, MORTAR, 10000)], [2, null]);
  });

  // Поправка времени полёта на превышение
  test("цель выше — прилёт раньше", () => {
    const s = solve(MORTAR, 1, 500, 0, 200);
    near(s.flightTime, 28.3 - 1.4);
    near(s.timeCorrection, -1.4);
    eq(s.baseFlightTime, 28.3);
  });
  test("цель ниже — прилёт позже", () => near(solve(MORTAR, 1, 500, 150, 50).flightTime, 28.3 + 0.7));
  test("интерполяция time_per_100", () => near(solve(SLEDGE, 2, 14650, 0, 100).timeCorrection, -0.6));
  test("без поправки — время по таблице", () => {
    const s = solve(MORTAR, 1, 500);
    eq([s.flightTime, s.baseFlightTime, s.timeCorrection], [28.3, 28.3, null]);
  });

  // Правила методички (те же случаи, что в tests/test_field_rules.py)
  const texts = (items) => items.map(([, t]) => t);
  test("с высотами — только разброс", () => {
    const items = F.advisories(MORTAR, 1, 1000, 100, 120);
    eq(items.length, 1);
    eq(items[0][0], "info");
  });
  test("без высот — напоминание", () => {
    const items = F.advisories(MORTAR, 1, 1000, null, null);
    eq(items[0], ["info", "Высоты не введены — поправка на превышение не учтена"]);
    eq(items.length, 2);
  });
  test("высокая цель — заряд 2", () => {
    eq(texts(F.advisories(MORTAR, 1, 1000, 0, 300)).filter((t) => t.includes("заряд 2")).length, 1);
    eq(texts(F.advisories(MORTAR, 2, 1000, 0, 300)).filter((t) => t.includes("заряд 2")).length, 0);
    eq(texts(F.advisories(SLEDGE, 0, 1000, 0, 500)).filter((t) => t.includes("заряд 2")).length, 0);
  });
  test("рекомендуемый заряд", () => {
    eq([F.recommendedCharge(D, MORTAR, 525), F.recommendedCharge(D, MORTAR, 400, 0, 100)], [1, 0]);
    eq([F.recommendedCharge(D, MORTAR, 525, 0, 340), F.recommendedCharge(D, MORTAR, 525, 0, 299)], [2, 1]);
    eq([F.recommendedCharge(D, MORTAR, 200, 0, 400), F.recommendedCharge(D, SLEDGE, 15000, 0, 500)], [0, 2]);
    eq(F.recommendedCharge(D, MORTAR, 10000), null);
  });
  test("Молот вместо Миномёта", () => eq([F.displayName(MORTAR), F.displayName(SLEDGE)], ["Молот", "Кувалда"]));

  const failed = results.filter((r) => !r.ok);
  root.TEST_RESULTS = { total: results.length, failed: failed.length, results };
  if (isNode) {
    for (const r of results) console.log(`${r.ok ? "ok  " : "FAIL"} ${r.name}${r.ok ? "" : " — " + r.error}`);
    console.log(`\n${results.length - failed.length}/${results.length} тестов прошло`);
    if (failed.length) process.exit(1);
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
