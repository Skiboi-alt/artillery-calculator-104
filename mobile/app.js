// Мобильная версия артиллерийского калькулятора 104-го ДОБ «Волчья стая».
// Логика и тексты повторяют программу для ПК (Calculator.py); расчёт — в ballistics.js.
(function () {
  "use strict";

  const B = window.Ballistics;
  const F = window.FieldRules;
  const DATA = window.WEAPON_DATA;
  const COLORS = window.THEME_COLORS;
  const MAX_SAVES = 10;
  const MAX_HISTORY = 20;
  const KEYS = { saves: "calc104.saves", settings: "calc104.settings", installHidden: "calc104.installHidden" };

  const $ = (id) => document.getElementById(id);
  const fields = {
    distance: $("distance"),
    user_height: $("user_height"),
    target_height: $("target_height"),
  };

  // ---------------------------------------------------------------- хранилище

  function readStore(key, fallback) {
    try {
      const value = JSON.parse(localStorage.getItem(key));
      return value && typeof value === "object" ? value : fallback;
    } catch (e) {
      return fallback;
    }
  }

  function writeStore(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (e) {
      return false;
    }
  }

  const settings = readStore(KEYS.settings, {});
  const saves = Object.fromEntries(
    Object.entries(readStore(KEYS.saves, {})).filter(([, v]) => v && typeof v === "object" && !Array.isArray(v))
  );

  const state = {
    weapon: DATA[settings.weapon] ? settings.weapon : "Миномёт",
    charge: String(settings.charge ?? "0"),
    // Заряд подбирается сам (самый быстрый), пока его не выбрали вручную
    chargeManual: Boolean(settings.charge_manual),
    history: Array.isArray(settings.history) ? settings.history.filter((h) => h && typeof h.elevation === "number") : [],
    shownElevation: null,
    resultText: "",
    infoText: "",
    lastSolution: null,
    adjust: null,          // { base, along, lateral } — корректировка относительно линии орудие–цель
    adjustStep: String(settings.adjust_step ?? "50"),
  };

  function persistSettings() {
    writeStore(KEYS.settings, {
      weapon: state.weapon,
      charge: state.charge,
      charge_manual: state.chargeManual,
      inputs: Object.fromEntries(Object.entries(fields).map(([k, el]) => [k, el.value])),
      history: state.history.slice(0, MAX_HISTORY),
      adjust_step: state.adjustStep,
      last_version: window.APP_INFO.version,
    });
  }

  // ---------------------------------------------------------------- эмблема

  function wolfSvg(fill, cutout, eyeRight) {
    const W = window.WOLF_SHAPES;
    const pts = (shape) => shape.map(([x, y]) => `${x},${y}`).join(" ");
    const poly = (shape, color) => `<polygon points="${pts(shape)}" fill="${color}"/>`;
    return `<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">${poly(W.outline, fill)}${
      W.cutouts.map((s) => poly(s, cutout)).join("")}${poly(W.leftEye, cutout)}${poly(W.rightEye, eyeRight || cutout)}</svg>`;
  }

  $("logo").innerHTML = wolfSvg(COLORS.accent, COLORS.surface_2, COLORS.error);
  $("watermarkWolf").innerHTML = wolfSvg(COLORS.watermark, COLORS.surface);

  // ---------------------------------------------------------------- переключатели

  function createSegmented(container, getValue, onSelect) {
    const indicator = document.createElement("div");
    indicator.className = "indicator";
    let options = [];
    let buttons = [];

    function update(instant) {
      const index = options.findIndex(([value]) => String(value) === String(getValue()));
      indicator.classList.toggle("instant", Boolean(instant));
      indicator.style.display = index < 0 ? "none" : "";
      indicator.style.width = `calc((100% - 8px) / ${Math.max(1, options.length)})`;
      indicator.style.transform = `translateX(${Math.max(0, index) * 100}%)`;
      buttons.forEach((button, i) => {
        button.classList.toggle("selected", i === index);
        button.setAttribute("aria-checked", String(i === index));
        button.tabIndex = i === index ? 0 : -1;
      });
      if (instant) requestAnimationFrame(() => indicator.classList.remove("instant"));
    }

    function setOptions(list) {
      options = list;
      container.innerHTML = "";
      container.appendChild(indicator);
      buttons = list.map(([value, label], i) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        button.setAttribute("role", "radio");
        button.addEventListener("click", () => select(i));
        button.addEventListener("keydown", (e) => {
          if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
            e.preventDefault();
            select(Math.min(options.length - 1, Math.max(0, i + (e.key === "ArrowRight" ? 1 : -1))));
            buttons[options.findIndex(([v]) => String(v) === String(getValue()))].focus();
          }
        });
        container.appendChild(button);
        return button;
      });
      update(true);
    }

    function select(i) {
      if (String(options[i][0]) !== String(getValue())) onSelect(options[i][0]);
    }

    // Подсветить подходящие варианты, остальные приглушить (null — убрать подсказку)
    function setSuggested(values) {
      const wanted = values ? new Set(values.map(String)) : null;
      buttons.forEach((button, i) => button.classList.toggle("ghost", Boolean(wanted) && !wanted.has(String(options[i][0]))));
    }

    return { setOptions, update, setSuggested };
  }

  const weaponSeg = createSegmented($("weaponSeg"), () => state.weapon, (v) => { state.weapon = v; onWeaponChange(); });
  const chargeSeg = createSegmented($("chargeSeg"), () => state.charge, (v) => { state.charge = String(v); state.chargeManual = true; chargeSeg.update(); updateChargeHint(); persistSettings(); });

  weaponSeg.setOptions(Object.keys(DATA).map((name) => [name, F.displayName(name)]));

  function onWeaponChange() {
    weaponSeg.update();
    const charges = B.allowedCharges(DATA, state.weapon).map(String);
    if (!charges.includes(state.charge)) state.charge = charges[0] || "";
    state.chargeManual = false; // Другое орудие — заряд снова подбирается сам
    chargeSeg.setOptions(charges.map((c) => [c, c]));
    updateChargeHint();
    persistSettings();
  }

  // ---------------------------------------------------------------- поправка и подсказки

  function parseNumber(text) {
    const value = Number(String(text).trim().replace(",", "."));
    return String(text).trim() !== "" && Number.isFinite(value) ? value : null;
  }

  function updateChargeHint() {
    const span = B.chargeRange(B.chargeRows(DATA, state.weapon, state.charge));
    $("chargeHint").textContent = span ? `Дальность ${span[0]} – ${span[1]} м${span[2] ? ` · шаг ${span[2]} м` : ""}` : "";

    // Какие заряды достают до введённой дистанции
    const suggestion = $("chargeSuggestion");
    const distance = parseNumber(fields.distance.value);
    suggestion.className = "";
    if (distance === null || distance <= 0) {
      chargeSeg.setSuggested(null);
      suggestion.textContent = "";
      return;
    }
    if (!state.chargeManual) autoSelectCharge(distance, ...enteredHeights());
    const suitable = B.chargesForDistance(DATA, state.weapon, distance).map(String);
    chargeSeg.setSuggested(suitable);
    if (!suitable.length) {
      suggestion.textContent = "ни один заряд не достаёт";
      suggestion.className = "bad";
    } else if (!suitable.includes(state.charge)) {
      suggestion.textContent = `не достаёт · подходят: ${suitable.join(", ")}`;
      suggestion.className = "bad";
    } else if (state.chargeManual) {
      suggestion.textContent = "выбран вручную";
    } else if (state.charge !== String(B.fastestCharge(DATA, state.weapon, distance))) {
      suggestion.textContent = "авто: цель выше на 300+ м";
    } else {
      suggestion.textContent = "авто: самый быстрый";
    }
  }

  // [высота орудия, высота цели], если обе введены числами, иначе [null, null]
  function enteredHeights() {
    const gun = parseNumber(fields.user_height.value), target = parseNumber(fields.target_height.value);
    return gun === null || target === null ? [null, null] : [gun, target];
  }

  // Правила методички: самый быстрый заряд, а при цели выше на 300+ м — заряд 2
  function autoSelectCharge(distance, gun = null, target = null) {
    const best = F.recommendedCharge(DATA, state.weapon, distance, gun, target);
    if (best !== null && String(best) !== state.charge) {
      state.charge = String(best);
      chargeSeg.update();
    }
  }

  // ---------------------------------------------------------------- уведомления и вибрация

  let toastTimer = null;
  function toast(message, type = "info") {
    const el = $("toast");
    el.className = `toast ${type}`;
    el.querySelector("span").textContent = message;
    requestAnimationFrame(() => el.classList.add("show"));
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 2200);
  }

  function vibrate(pattern) {
    // Браузер разрешает вибрацию только после касания экрана
    const touched = !navigator.userActivation || navigator.userActivation.hasBeenActive;
    if (navigator.vibrate && touched) {
      try { navigator.vibrate(pattern); } catch (e) { /* не поддерживается */ }
    }
  }

  // ---------------------------------------------------------------- результат

  const card = $("resultCard");
  const resValue = $("resValue");
  let numberAnimation = null;

  function flash(kind) {
    card.classList.remove("flash", "flash-error");
    void card.offsetWidth; // Перезапуск CSS-анимации
    card.classList.add(kind === "error" ? "flash-error" : "flash");
  }

  function animateNumber(from, to) {
    cancelAnimationFrame(numberAnimation);
    const started = performance.now();
    const duration = 450;
    const step = (now) => {
      const p = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      resValue.textContent = (from + (to - from) * eased).toFixed(1);
      if (p < 1) numberAnimation = requestAnimationFrame(step);
    };
    numberAnimation = requestAnimationFrame(step);
  }

  function setPill(text, kind) {
    const pill = $("pill");
    pill.textContent = text;
    pill.className = `pill ${kind}`;
  }

  function resetStats() {
    stopTimer();
    state.lastSolution = null;
    $("resTime").textContent = "—";
    $("resCorr").textContent = "—";
    $("resTime").className = $("resCorr").className = "stat-value";
    $("resDetail").textContent = "";
    $("timerNote").textContent = "";
    $("resGame").hidden = true;
    $("corrNote").textContent = "";
    renderComparison([], null);
    renderAdvice([]);
  }

  function renderAdvice(items) {
    const list = $("adviceList");
    list.innerHTML = "";
    for (const [level, text] of items) {
      const li = document.createElement("li");
      li.className = level;
      li.textContent = text;
      list.appendChild(li);
    }
  }

  function showEmpty() {
    cancelAnimationFrame(numberAnimation);
    state.shownElevation = null;
    setPill("Ожидание", "");
    resValue.textContent = "—";
    resValue.className = "";
    $("resMessage").textContent = "Заполните параметры и нажмите «Рассчитать»";
    $("resMessage").className = "res-message";
    resetStats();
    state.resultText = state.infoText = "";
  }

  function showError(title, details) {
    cancelAnimationFrame(numberAnimation);
    state.shownElevation = null;
    setPill("Ошибка", "error");
    resValue.textContent = "—";
    resValue.className = "error";
    $("resMessage").textContent = `${title}. ${details}`;
    $("resMessage").className = "res-message error";
    resetStats();
    flash("error");
    state.resultText = `❌ ${title}`;
    state.infoText = details;
  }

  function showResult(solution, charge, distance, animate, comparison = [], advice = []) {
    stopTimer();
    state.lastSolution = solution;
    setPill(solution.lowerRow === solution.upperRow ? "Таблица" : "Интерполяция", "ok");
    const target = solution.elevation;
    resValue.className = "ok";
    if (animate) {
      // Число плавно «докручивается» от прошлого значения до нового
      animateNumber(state.shownElevation ?? target - 40, target);
      flash("ok");
    } else {
      resValue.textContent = target.toFixed(1);
    }
    state.shownElevation = target;

    const direction = adjustDirectionText();
    $("resMessage").textContent = `${F.displayName(state.weapon)} · заряд ${charge} · ${B.g(distance)} м${direction ? ` · направление ${direction}` : ""}`;
    $("resMessage").className = "res-message";
    renderComparison(comparison, charge);
    renderAdvice(advice);
    // «Что выставить в игре» — в порядке действий по методичке (тестовая функция)
    $("resGame").textContent = `В игре: ELV ${solution.elevation.toFixed(1)} · заряд ${charge} (F) · прилёт ${solution.flightTime.toFixed(0)} с`;
    $("resGame").hidden = false;
    const { lowerRow: lo, upperRow: up } = solution;
    $("resDetail").textContent = lo === up
      ? `Строка таблицы: ${lo.range} м → ${lo.elev} MIL`
      : `Между строками ${lo.range} м → ${lo.elev} и ${up.range} м → ${up.elev} MIL`;

    $("resTime").textContent = `${solution.flightTime.toFixed(1)} с`;
    $("resTime").className = "stat-value on";
    $("timerNote").textContent = "▶ таймер";
    if (solution.correction === null) {
      $("resCorr").textContent = "выкл";
      $("resCorr").className = "stat-value";
      $("corrNote").textContent = "";
      state.resultText = `🎯 ${target.toFixed(1)} MIL | ⏱️  ${solution.flightTime.toFixed(1)} сек`;
      state.infoText = `Заряд: ${charge} | Расстояние: ${Math.round(distance)}м`;
    } else {
      const sign = solution.correction >= 0 ? "+" : "";
      $("resCorr").textContent = `${sign}${solution.correction.toFixed(1)} MIL`;
      $("resCorr").className = "stat-value on";
      // Поправка времени полёта на превышение (4-й столбец таблицы)
      const tc = solution.timeCorrection;
      $("corrNote").textContent = `время ${tc >= 0 ? "+" : "−"}${Math.abs(tc).toFixed(1)} с`;
      state.resultText = `✈️  ${target.toFixed(1)} MIL | ⏱️  ${solution.flightTime.toFixed(1)} сек`;
      state.infoText = `Базовое: ${solution.baseElevation.toFixed(1)} MIL | Поправка на высоту: ${sign}${solution.correction.toFixed(1)} MIL`;
    }
  }

  // ---------------------------------------------------------------- расчёт

  class InputError extends Error {
    constructor(message, field) { super(message); this.field = field; }
  }

  function validateInputs() {
    function number(name, title, required) {
      const text = fields[name].value.trim();
      if (!text) {
        if (required) throw new InputError(`Заполните поле «${title}»`, name);
        return null;
      }
      const value = parseNumber(text);
      if (value === null) throw new InputError(`${title}: введите число`, name);
      return value;
    }

    const charges = B.allowedCharges(DATA, state.weapon);
    const charge = Number(state.charge);
    if (!charges.includes(charge)) throw new InputError("Выберите заряд");

    // Высоты необязательны: обе — поправка на превышение, ни одной — без поправки
    const distance = number("distance", "Дистанция до цели", true);
    const gun = number("user_height", "Высота орудия", false);
    const target = number("target_height", "Высота цели", false);
    if (distance <= 0) throw new InputError("Дистанция должна быть больше 0", "distance");
    if ((gun === null) !== (target === null)) {
      throw new InputError("Введите обе высоты или оставьте обе пустыми", gun === null ? "user_height" : "target_height");
    }
    if (gun !== null && gun < 0) throw new InputError("Высота орудия не может быть отрицательной", "user_height");
    if (target !== null && target < 0) throw new InputError("Высота цели не может быть отрицательной", "target_height");
    return { distance, charge, gun, target };
  }

  function markError(name) {
    const field = fields[name].closest(".field");
    field.classList.add("error");
    fields[name].focus();
  }

  function calculate(silent = false) {
    let input;
    try {
      input = validateInputs();
    } catch (e) {
      if (!(e instanceof InputError)) throw e;
      if (silent) {
        showEmpty();
      } else {
        if (e.field) markError(e.field);
        toast(e.message, "error");
        vibrate([30, 50, 30]);
      }
      return;
    }

    if (!state.chargeManual) {
      autoSelectCharge(input.distance, input.gun, input.target);
      input.charge = Number(state.charge);
      updateChargeHint();
    }
    let solution;
    try {
      solution = B.solve(DATA, state.weapon, input.charge, input.distance, input.gun, input.target);
    } catch (e) {
      if (!(e instanceof B.OutOfTableError)) throw e;
      showError(e.title, e.details);
      if (!silent) vibrate([30, 50, 30]);
      return;
    }

    const comparison = B.compareCharges(DATA, state.weapon, input.distance, input.gun, input.target);
    const advice = F.advisories(state.weapon, input.charge, input.distance, input.gun, input.target);
    showResult(solution, input.charge, input.distance, !silent, comparison, advice);
    addHistory(solution, input.charge, input.distance);
    persistSettings();
    if (!silent) {
      vibrate(15);
      if (document.activeElement && document.activeElement.tagName === "INPUT") document.activeElement.blur();
    }
  }

  // ---------------------------------------------------------------- история

  function snapshot() {
    return {
      distance: fields.distance.value,
      charge: state.charge,
      user_height: fields.user_height.value,
      target_height: fields.target_height.value,
      weapon: state.weapon,
    };
  }

  function addHistory(solution, charge, distance) {
    let summary = `${F.displayName(state.weapon)} · з${charge} · ${B.g(distance)} м`;
    if (solution.correction !== null) {
      // Разница высот — чтобы отличать расчёты одной дистанции с поправкой и без
      const diff = (parseNumber(fields.target_height.value) || 0) - (parseNumber(fields.user_height.value) || 0);
      summary += ` · Δh ${diff >= 0 ? "+" : ""}${B.g(diff)}`;
    }
    const now = new Date();
    const entry = Object.assign(snapshot(), {
      elevation: Math.round(solution.elevation * 10) / 10,
      time: `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`,
      summary,
    });
    // Повтор того же расчёта не дублируем — поднимаем наверх
    const key = (h) => [h.weapon, h.charge, h.distance, h.elevation].join("|");
    state.history = [entry, ...state.history.filter((h) => key(h) !== key(entry))].slice(0, MAX_HISTORY);
    renderHistory();
  }

  function renderHistory() {
    const list = $("historyList");
    list.innerHTML = "";
    for (const item of state.history.slice(0, 8)) {
      const li = document.createElement("li");
      li.innerHTML = `<span class="h-value"></span><span class="h-summary"></span><span class="h-time"></span>`;
      li.querySelector(".h-value").innerHTML = `${item.elevation.toFixed(1)}<small>MIL</small>`;
      li.querySelector(".h-summary").textContent = item.summary || "";
      li.querySelector(".h-time").textContent = item.time || "";
      li.addEventListener("click", () => {
        applyValues(item);
        calculate(true);
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
      list.appendChild(li);
    }
    const empty = state.history.length === 0;
    $("historyEmpty").hidden = !empty;
    $("historyClear").hidden = empty;
  }

  $("historyClear").addEventListener("click", async () => {
    if (await confirmSheet("Очистить историю?", "Список последних расчётов будет удалён.", "Очистить", true)) {
      state.history = [];
      renderHistory();
      persistSettings();
    }
  });

  function applyValues(data) {
    state.weapon = DATA[data.weapon] ? data.weapon : "Миномёт";
    const charges = B.allowedCharges(DATA, state.weapon).map(String);
    const charge = String(data.charge ?? "").trim();
    state.charge = charges.includes(charge) ? charge : charges[0];
    onWeaponChange();
    state.chargeManual = charges.includes(charge); // Сохранённый расчёт повторяется с тем же зарядом
    for (const name of Object.keys(fields)) {
      fields[name].value = String(data[name] ?? "");
      fields[name].closest(".field").classList.remove("error");
    }
    updateChargeHint();
  }

  // ---------------------------------------------------------------- нижняя панель (диалоги)

  const sheet = $("sheet");
  const backdrop = $("sheetBackdrop");
  let closeCurrent = null;

  function openSheet(html, onClose) {
    sheet.innerHTML = html;
    sheet.classList.add("open");
    backdrop.classList.add("open");
    closeCurrent = onClose;
  }

  function closeSheet() {
    sheet.classList.remove("open");
    backdrop.classList.remove("open");
    const callback = closeCurrent;
    closeCurrent = null;
    if (callback) callback();
  }

  backdrop.addEventListener("click", closeSheet);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && sheet.classList.contains("open")) closeSheet(); });

  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function confirmSheet(title, message, confirmText, danger = false) {
    return new Promise((resolve) => {
      let answer = false;
      openSheet(`
        <h2>${escapeHtml(title)}</h2><p>${escapeHtml(message)}</p>
        <div class="buttons">
          <button class="btn secondary" data-act="cancel" type="button">Отмена</button>
          <button class="btn ${danger ? "danger" : "primary"}" data-act="ok" type="button">${escapeHtml(confirmText)}</button>
        </div>`, () => resolve(answer));
      sheet.querySelector('[data-act="cancel"]').onclick = closeSheet;
      sheet.querySelector('[data-act="ok"]').onclick = () => { answer = true; closeSheet(); };
    });
  }

  function askString(title, label) {
    return new Promise((resolve) => {
      let answer = null;
      openSheet(`
        <h2>${escapeHtml(title)}</h2>
        <label class="field" for="sheetInput" style="margin-top:12px">
          <span class="caption">${escapeHtml(label)}</span>
          <span class="input-wrap"><input id="sheetInput" type="text" enterkeyhint="done" autocomplete="off" maxlength="40"></span>
        </label>
        <div class="buttons">
          <button class="btn secondary" data-act="cancel" type="button">Отмена</button>
          <button class="btn primary" data-act="ok" type="button">Сохранить</button>
        </div>`, () => resolve(answer));
      const input = sheet.querySelector("#sheetInput");
      const submit = () => { answer = input.value; closeSheet(); };
      sheet.querySelector('[data-act="cancel"]').onclick = closeSheet;
      sheet.querySelector('[data-act="ok"]').onclick = submit;
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") submit(); });
      setTimeout(() => input.focus(), 280);
    });
  }

  // ---------------------------------------------------------------- сохранения

  function writeSaves() {
    if (!writeStore(KEYS.saves, saves)) {
      toast("Не удалось записать сохранения", "error");
      return false;
    }
    updateSavesBadge();
    return true;
  }

  function updateSavesBadge() {
    const count = Object.keys(saves).length;
    const badge = $("savesCount");
    badge.hidden = count === 0;
    badge.textContent = `${count}/${MAX_SAVES}`;
  }

  async function saveCurrent() {
    let name = await askString("Сохранить значения", "Название");
    if (name === null) return;
    name = name.trim();
    if (!name) return;
    if (!(name in saves) && Object.keys(saves).length >= MAX_SAVES) {
      toast(`Максимум ${MAX_SAVES} сохранений`, "error");
      return;
    }
    if (name in saves && !(await confirmSheet("Перезаписать?", `Сохранение «${name}» уже существует и будет заменено.`, "Перезаписать"))) {
      return;
    }
    saves[name] = Object.assign(snapshot(), { result: state.resultText, info: state.infoText });
    if (writeSaves()) toast(`Сохранено «${name}»`, "success");
  }

  function describeSave(data) {
    const parts = [F.displayName(String(data.weapon || "Миномёт"))];
    if (String(data.charge ?? "").trim()) parts.push(`заряд ${data.charge}`);
    if (String(data.distance ?? "").trim()) parts.push(`${data.distance} м`);
    return parts.join(" · ");
  }

  function openSaves() {
    const names = Object.keys(saves);
    let selected = names[0] ?? null;
    const items = names.map((name) => `
      <li data-name="${escapeHtml(name)}"><b>${escapeHtml(name)}</b><small>${escapeHtml(describeSave(saves[name]))}</small></li>`).join("");
    openSheet(`
      <h2>Сохранения</h2>
      <p>${names.length ? "Нажмите, чтобы выбрать; двойное нажатие — загрузить." : "Сохранений пока нет."}</p>
      ${names.length ? `<ul class="save-list">${items}</ul>` : ""}
      ${names.length ? `<div class="buttons">
        <button class="btn danger" data-act="delete" type="button">Удалить</button>
        <button class="btn primary" data-act="load" type="button">Загрузить</button>
      </div>` : ""}
      <div class="tools">
        <button class="btn secondary small" data-act="import" type="button">Импорт saves.json</button>
        <button class="btn secondary small" data-act="export" type="button" ${names.length ? "" : "disabled"}>Экспорт</button>
      </div>`);

    const paint = () => sheet.querySelectorAll(".save-list li").forEach((li) => li.classList.toggle("selected", li.dataset.name === selected));
    paint();
    sheet.querySelectorAll(".save-list li").forEach((li) => {
      li.addEventListener("click", () => { selected = li.dataset.name; paint(); });
      li.addEventListener("dblclick", () => { selected = li.dataset.name; load(); });
    });

    function load() {
      if (selected === null) return;
      const name = selected;
      closeSheet();
      applyValues(saves[name]);
      calculate(true);
      toast(`Загружено «${name}»`, "success");
    }

    const act = (name) => sheet.querySelector(`[data-act="${name}"]`);
    if (act("load")) act("load").onclick = load;
    if (act("delete")) {
      act("delete").onclick = async () => {
        if (selected === null) return;
        const name = selected;
        const ok = await confirmSheet("Удалить сохранение?", `«${name}» будет удалено без возможности восстановления.`, "Удалить", true);
        if (ok) {
          delete saves[name];
          writeSaves();
          toast(`Сохранение «${name}» удалено`, "success");
        }
        if (Object.keys(saves).length) setTimeout(openSaves, 300);
      };
    }
    act("import").onclick = () => $("importFile").click();
    act("export").onclick = exportSaves;
  }

  // Файл в том же формате, что saves.json программы для ПК
  function exportSaves() {
    const blob = new Blob([JSON.stringify(saves, null, 2)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "saves.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
  }

  $("importFile").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    let data;
    try {
      data = JSON.parse(await file.text());
    } catch (err) {
      toast("Файл повреждён или это не JSON", "error");
      return;
    }
    if (!data || typeof data !== "object" || Array.isArray(data)) {
      toast("Неверный формат файла сохранений", "error");
      return;
    }
    let added = 0, skipped = 0;
    for (const [name, value] of Object.entries(data)) {
      if (!value || typeof value !== "object" || Array.isArray(value)) continue;
      if (!(name in saves) && Object.keys(saves).length >= MAX_SAVES) { skipped++; continue; }
      saves[name] = value;
      added++;
    }
    writeSaves();
    closeSheet();
    toast(skipped ? `Импортировано ${added}, не поместилось ${skipped}` : `Импортировано сохранений: ${added}`,
          skipped ? "error" : "success");
  });

  // ---------------------------------------------------------------- сравнение зарядов

  function renderComparison(comparison, currentCharge) {
    const row = $("compareRow");
    row.innerHTML = "";
    if (comparison.length < 2) return;
    // Правило из методички: меньший заряд — снаряд летит быстрее
    const fastest = comparison.reduce((a, b) => (b[1].flightTime < a[1].flightTime ? b : a))[0];
    for (const [charge, s] of comparison) {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = `chip${charge === currentCharge ? " active" : ""}`;
      chip.innerHTML = `<b>з${charge}</b>${s.elevation.toFixed(1)} · ${s.flightTime.toFixed(0)} с${charge === fastest ? "<em>быстрее</em>" : ""}`;
      chip.addEventListener("click", () => {
        state.charge = String(charge);
        state.chargeManual = true;
        chargeSeg.update();
        updateChargeHint();
        calculate();
      });
      row.appendChild(chip);
    }
  }

  // ---------------------------------------------------------------- корректировка огня

  function adjustDirectionText() {
    if (!state.adjust || !state.adjust.lateral) return "";
    const mils = B.adjustFire(state.adjust.base, state.adjust.along, state.adjust.lateral)[1];
    return `${Math.abs(mils).toFixed(1)} MIL ${mils > 0 ? "вправо" : "влево"}`;
  }

  function updateAdjustStatus() {
    const status = $("adjustStatus"), direction = $("adjustDirection");
    if (!state.adjust) {
      status.textContent = "";
      direction.textContent = "Недолёт — дальше, перелёт — ближе";
      direction.className = "adjust-direction";
      return;
    }
    const { along, lateral } = state.adjust;
    const parts = [];
    if (along) parts.push(`${B.g(Math.abs(along))} м ${along > 0 ? "дальше" : "ближе"}`);
    if (lateral) parts.push(`${B.g(Math.abs(lateral))} м ${lateral > 0 ? "правее" : "левее"}`);
    status.textContent = parts.join(" · ") || "без сдвига";
    if (lateral) {
      const mils = B.adjustFire(state.adjust.base, along, lateral)[1];
      direction.textContent = `Направление ${mils > 0 ? "+" : "−"}${Math.abs(mils).toFixed(1)} MIL`;
      direction.className = "adjust-direction on";
    } else {
      direction.textContent = "Направление без изменений";
      direction.className = "adjust-direction";
    }
  }

  function adjustFire(kind) {
    const step = parseNumber($("adjustStep").value);
    if (step === null || step <= 0) {
      $("adjustStep").focus();
      toast("Шаг корректировки: введите число больше 0", "error");
      return;
    }
    if (!state.adjust) {
      const base = parseNumber(fields.distance.value);
      if (base === null || base <= 0) {
        markError("distance");
        toast("Сначала введите дистанцию до цели", "error");
        return;
      }
      state.adjust = { base, along: 0, lateral: 0 };
    }
    const [key, sign] = { short: ["along", 1], over: ["along", -1], left: ["lateral", -1], right: ["lateral", 1] }[kind];
    state.adjust[key] += sign * step;

    const distance = Math.round(B.adjustFire(state.adjust.base, state.adjust.along, state.adjust.lateral)[0] * 10) / 10;
    fields.distance.value = B.g(distance);
    updateAdjustStatus();
    updateChargeHint();
    calculate();
  }

  function resetAdjust() {
    if (!state.adjust) return;
    fields.distance.value = B.g(state.adjust.base);
    state.adjust = null;
    updateAdjustStatus();
    updateChargeHint();
    calculate(true);
  }

  document.querySelectorAll("[data-adjust]").forEach((button) => {
    button.addEventListener("click", () => adjustFire(button.dataset.adjust));
  });
  $("adjustReset").addEventListener("click", resetAdjust);
  $("adjustStep").value = state.adjustStep;
  $("adjustStep").addEventListener("input", () => { state.adjustStep = $("adjustStep").value; persistSettings(); });

  // ---------------------------------------------------------------- таймер полёта

  const SPLASH_WARNING_S = 5; // Сигнал «скоро разрыв» за 5 секунд
  let timerFrame = null, timerEnd = 0, timerWarned = false, audio = null;

  function beep(frequency, durationMs) {
    try {
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      const osc = audio.createOscillator(), gain = audio.createGain();
      osc.frequency.value = frequency;
      gain.gain.setValueAtTime(0.25, audio.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audio.currentTime + durationMs / 1000);
      osc.connect(gain).connect(audio.destination);
      osc.start();
      osc.stop(audio.currentTime + durationMs / 1000);
    } catch (e) { /* звук недоступен */ }
  }

  function toggleTimer() {
    if (timerFrame !== null) {
      stopTimer();
      showFlightTime();
      return;
    }
    if (!state.lastSolution) {
      toast("Сначала выполните расчёт", "error");
      return;
    }
    timerEnd = performance.now() + state.lastSolution.flightTime * 1000;
    timerWarned = false;
    $("timerBtn").classList.add("running");
    beep(1200, 80);
    vibrate(20);
    tick();
  }

  function tick() {
    const remaining = (timerEnd - performance.now()) / 1000;
    const btn = $("timerBtn");
    if (remaining <= 0) {
      stopTimer();
      beep(900, 600);
      vibrate([200, 80, 200]);
      toast("Разрыв!", "success");
      btn.classList.remove("flash"); void btn.offsetWidth; btn.classList.add("flash");
      showFlightTime();
      return;
    }
    if (remaining <= SPLASH_WARNING_S && !timerWarned) {
      timerWarned = true;
      beep(1500, 150);
      vibrate(60);
    }
    btn.classList.toggle("warn", remaining <= SPLASH_WARNING_S);
    $("resTime").textContent = `${remaining.toFixed(1)} с`;
    $("timerNote").textContent = remaining <= SPLASH_WARNING_S ? "скоро разрыв!" : "до разрыва · стоп";
    timerFrame = requestAnimationFrame(tick);
  }

  function stopTimer() {
    if (timerFrame !== null) cancelAnimationFrame(timerFrame);
    timerFrame = null;
    $("timerBtn").classList.remove("running", "warn");
  }

  function showFlightTime() {
    if (!state.lastSolution) return;
    $("resTime").textContent = `${state.lastSolution.flightTime.toFixed(1)} с`;
    $("timerNote").textContent = "▶ таймер";
  }

  $("timerBtn").addEventListener("click", toggleTimer);

  // ---------------------------------------------------------------- справка и «Что нового»

  const HELP = [
    ["Порядок расчёта", "Выберите орудие, введите дистанцию и нажмите «Рассчитать». Заряд подбирается сам — самый быстрый из подходящих, как советует методичка; другой можно выбрать вручную или нажатием в строке зарядов. Значение всегда по таблице: на табличной дальности — строка таблицы, между строками — интерполяция."],
    ["Поправка на превышение", "Включается сама, когда заполнены обе высоты — орудия и цели (с карты, над уровнем моря). Цель выше — возвышение уменьшается, ниже — увеличивается. Время полёта тоже поправляется по 4-му столбцу таблицы: цель выше — прилёт раньше. Пустые поля — расчёт без поправки."],
    ["Подсказки под результатом", "Напоминания из методички: высоты не введены; цель выше на 300 м и больше — для Молота нужен заряд 2; разброс до 20 м — проверьте, что союзников нет рядом с целью."],
    ["Корректировка огня", "После выстрела по докладу наблюдателя: «Недолёт» — дальше на шаг, «Перелёт» — ближе, «Левее»/«Правее» — сместить разрыв вбок. Сдвиги — относительно линии орудие–цель; дистанция пересчитывается, поправку направления (в милах, 6400 в круге) внесите в азимут. «Сброс» возвращает исходную дистанцию."],
    ["Таймер полёта", "Нажмите на «Время полёта» — обратный отсчёт до разрыва. Короткий сигнал за 5 секунд, длинный — в момент разрыва (и вибрация на Android). Повторное нажатие — стоп."],
    ["Сохранения", "Значок папки — список сохранений, импорт и экспорт saves.json: формат общий с программой для ПК."],
  ];

  function showHelp() {
    const sections = HELP.map(([title, text]) =>
      `<div class="help-section"><span class="caption">${escapeHtml(title)}</span><p>${escapeHtml(text)}</p></div>`).join("");
    openSheet(`
      <h2>Справка</h2>
      <p>Артиллерийский калькулятор 104-го ДОБ · версия ${escapeHtml(window.APP_INFO.version)} · сделано SmaleUp</p>
      ${sections}
      <div class="links"><a href="https://github.com/${escapeHtml(window.APP_INFO.repository)}" target="_blank" rel="noopener">Проект на GitHub</a></div>
      <div class="buttons">
        <button class="btn secondary" data-act="news" type="button">Что нового</button>
        <button class="btn primary" data-act="close" type="button">Закрыть</button>
      </div>`);
    sheet.querySelector('[data-act="close"]').onclick = closeSheet;
    sheet.querySelector('[data-act="news"]').onclick = () => { closeSheet(); setTimeout(showWhatsNew, 300); };
  }

  function showWhatsNew() {
    const version = window.APP_INFO.version;
    const items = (window.APP_INFO.whatsNew[version] || []).map((t) => `<li>${escapeHtml(t)}</li>`).join("");
    openSheet(`
      <h2>Что нового в версии ${escapeHtml(version)}</h2>
      <ul class="news">${items}</ul>
      <div class="buttons" style="grid-template-columns:1fr">
        <button class="btn primary" data-act="close" type="button">Понятно</button>
      </div>`);
    sheet.querySelector('[data-act="close"]').onclick = closeSheet;
  }

  $("helpBtn").addEventListener("click", showHelp);

  // ---------------------------------------------------------------- установка на телефон

  let installEvent = null;
  const standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  const isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);

  function showInstall(text, withButton) {
    if (standalone || localStorage.getItem(KEYS.installHidden)) return;
    $("installText").textContent = text;
    $("installBtn").hidden = !withButton;
    $("installCard").hidden = false;
  }

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    installEvent = e;
    showInstall("Будет работать без интернета, как обычное приложение.", true);
  });
  if (isIOS) showInstall("В Safari нажмите «Поделиться» → «На экран «Домой»».", false);

  $("installBtn").addEventListener("click", async () => {
    if (!installEvent) return;
    installEvent.prompt();
    await installEvent.userChoice;
    installEvent = null;
    $("installCard").hidden = true;
  });
  $("installClose").addEventListener("click", () => {
    $("installCard").hidden = true;
    try { localStorage.setItem(KEYS.installHidden, "1"); } catch (e) { /* приватный режим */ }
  });

  // На localhost офлайн-кэш мешает видеть правки — включается только с ?sw=1
  const isLocal = ["localhost", "127.0.0.1"].includes(location.hostname) && !location.search.includes("sw=1");
  if ("serviceWorker" in navigator && location.protocol !== "file:" && !isLocal) {
    navigator.serviceWorker.register("sw.js").catch(() => { /* офлайн-режим недоступен */ });
  }

  // ---------------------------------------------------------------- запуск

  for (const [name, input] of Object.entries(fields)) {
    input.value = String((settings.inputs || {})[name] ?? "");
    input.addEventListener("input", () => {
      input.closest(".field").classList.remove("error");
      if (name === "distance") {
        state.chargeManual = false; // Новая дистанция — заряд снова подбирается сам
        // Дистанцию изменили вручную — прежняя корректировка к ней больше не относится
        if (state.adjust) { state.adjust = null; updateAdjustStatus(); }
        updateChargeHint();
      }
    });
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); calculate(); } });
    input.addEventListener("change", persistSettings);
  }

  $("calcBtn").addEventListener("click", () => calculate());
  $("saveBtn").addEventListener("click", saveCurrent);
  $("savesBtn").addEventListener("click", openSaves);
  document.addEventListener("visibilitychange", () => { if (document.hidden) persistSettings(); });

  const problems = B.validateWeaponData(DATA);
  if (problems.length) console.warn("Таблицы:", problems);

  onWeaponChange();
  updateSavesBadge();
  renderHistory();
  showEmpty();

  // «Что нового» — только для тех, кто уже пользовался прошлой версией
  if (settings.history && settings.last_version !== window.APP_INFO.version) setTimeout(showWhatsNew, 700);
  persistSettings();

  // Для отладки и автоматических проверок
  window.App = { state, calculate, applyValues, saves };
})();
