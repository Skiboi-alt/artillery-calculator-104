// Тесты расчёта мобильной версии — те же случаи, что в tests/test_ballistics.py.
// Запуск: node mobile/tests/ballistics.test.js  или откройте mobile/tests.html в браузере.
(function (root) {
  "use strict";
  const isNode = typeof module !== "undefined" && module.exports;
  if (isNode) {
    require("../data.js");
    require("../ballistics.js");
  }
  const B = root.Ballistics;
  const D = root.WEAPON_DATA;
  const MORTAR = "Миномёт", SLEDGE = "Кувалда";
  const solve = (w, c, d, m, gun = 0, target = 0, corr = false) => B.solve(D, w, c, d, m, gun, target, corr);

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
    const s = solve(MORTAR, 1, 500, "table");
    eq([s.elevation, s.flightTime, s.correction], [1471, 28.3, null]);
  });
  test("дробная запись дистанции", () => eq(solve(MORTAR, 1, 500.0, "table").elevation, 1471));
  test("Кувалда", () => {
    const s = solve(SLEDGE, 3, 15000, "table");
    eq([s.elevation, s.flightTime], [1418, 130.0]);
  });
  test("нет строки в таблице", () => throwsOut(() => solve(MORTAR, 1, 525, "table"), "Нет табличного значения"));

  // Интерполяция
  test("середина между строками", () => {
    const s = solve(MORTAR, 1, 525, "nontable");
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
    const s = solve(MORTAR, 1, 500, "nontable");
    eq(s.elevation, 1471);
    if (s.lowerRow !== s.upperRow) throw new Error("строки должны совпадать");
  });
  test("края таблицы", () => {
    eq(solve(MORTAR, 1, 150, "nontable").elevation, 1562);
    eq(solve(MORTAR, 1, 1950, "nontable").elevation, 913);
  });
  test("вне диапазона", () => {
    for (const d of [149.9, 1950.1, 5000]) throwsOut(() => solve(MORTAR, 1, d, "nontable"), "Вне диапазона");
  });

  // Поправка на превышение
  test("цель выше — возвышение меньше", () => {
    const s = solve(MORTAR, 1, 500, "table", 0, 100, true);
    near(s.elevation, 1471 - 3.2);
    near(s.correction, -3.2);
    eq(s.baseElevation, 1471);
  });
  test("цель ниже — возвышение больше", () => {
    const s = solve(MORTAR, 1, 525, "nontable", 120, 80, true);
    near(s.correction, 0.4 * (3.2 + 3.5) / 2);
    near(s.elevation, 1464.5 + 1.34);
  });
  test("равные высоты", () => eq(B.heightCorrection(1000, 5.0, 50, 50), [1000, 0]));
  test("нет delev", () => eq(B.heightCorrection(1000, null, 0, 10), [1000, 0]));
  test("поправка выключена", () => {
    const s = solve(MORTAR, 1, 500, "table", 0, 500, false);
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

  const failed = results.filter((r) => !r.ok);
  root.TEST_RESULTS = { total: results.length, failed: failed.length, results };
  if (isNode) {
    for (const r of results) console.log(`${r.ok ? "ok  " : "FAIL"} ${r.name}${r.ok ? "" : " — " + r.error}`);
    console.log(`\n${results.length - failed.length}/${results.length} тестов прошло`);
    if (failed.length) process.exit(1);
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
