// Мобильная версия артиллерийского калькулятора 104-го ДОБ «Волчья стая».
// Логика и тексты повторяют программу для ПК (Calculator.py); расчёт — в ballistics.js.
(function () {
  "use strict";

  const B = window.Ballistics;
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
    mode: settings.calculation_mode === "nontable" ? "nontable" : "table",
    correction: Boolean(settings.apply_height_correction),
    history: Array.isArray(settings.history) ? settings.history.filter((h) => h && typeof h.elevation === "number") : [],
    shownElevation: null,
    resultText: "",
    infoText: "",
  };

  function persistSettings() {
    writeStore(KEYS.settings, {
      weapon: state.weapon,
      charge: state.charge,
      calculation_mode: state.mode,
      apply_height_correction: state.correction,
      inputs: Object.fromEntries(Object.entries(fields).map(([k, el]) => [k, el.value])),
      history: state.history.slice(0, MAX_HISTORY),
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
  const chargeSeg = createSegmented($("chargeSeg"), () => state.charge, (v) => { state.charge = String(v); chargeSeg.update(); updateChargeHint(); persistSettings(); });
  const modeSeg = createSegmented($("modeSeg"), () => state.mode, (v) => { state.mode = v; modeSeg.update(); persistSettings(); });

  weaponSeg.setOptions(Object.keys(DATA).map((name) => [name, name]));
  modeSeg.setOptions([["table", "По таблице"], ["nontable", "Интерполяция"]]);

  function onWeaponChange() {
    weaponSeg.update();
    const charges = B.allowedCharges(DATA, state.weapon).map(String);
    if (!charges.includes(state.charge)) state.charge = charges[0] || "";
    chargeSeg.setOptions(charges.map((c) => [c, c]));
    updateChargeHint();
    persistSettings();
  }

  // ---------------------------------------------------------------- поправка и подсказки

  const correctionBox = $("correction");
  correctionBox.checked = state.correction;
  correctionBox.addEventListener("change", () => {
    state.correction = correctionBox.checked;
    updateHeightsDim();
    persistSettings();
  });

  function updateHeightsDim() {
    // Высоты нужны только при включённой поправке — иначе поля приглушены
    $("heights").classList.toggle("dimmed", !state.correction);
  }

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
    const suitable = B.chargesForDistance(DATA, state.weapon, distance).map(String);
    chargeSeg.setSuggested(suitable);
    if (!suitable.length) {
      suggestion.textContent = "ни один заряд не достаёт";
      suggestion.className = "bad";
    } else if (suitable.includes(state.charge)) {
      suggestion.textContent = "заряд подходит";
    } else {
      suggestion.textContent = `подходят: ${suitable.join(", ")}`;
      suggestion.className = "good";
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
    $("resTime").textContent = "—";
    $("resCorr").textContent = "—";
    $("resTime").className = $("resCorr").className = "stat-value";
    $("resDetail").textContent = "";
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

  function showResult(solution, charge, distance, animate) {
    setPill(state.mode === "table" ? "Таблица" : "Интерполяция", "ok");
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

    $("resMessage").textContent = `${state.weapon} · заряд ${charge} · ${B.g(distance)} м`;
    $("resMessage").className = "res-message";
    const { lowerRow: lo, upperRow: up } = solution;
    $("resDetail").textContent = lo === up
      ? `Строка таблицы: ${lo.range} м → ${lo.elev} MIL`
      : `Между строками ${lo.range} м → ${lo.elev} и ${up.range} м → ${up.elev} MIL`;

    $("resTime").textContent = `${solution.flightTime.toFixed(1)} с`;
    $("resTime").className = "stat-value on";
    if (solution.correction === null) {
      $("resCorr").textContent = "выкл";
      $("resCorr").className = "stat-value";
      state.resultText = `🎯 ${target.toFixed(1)} MIL | ⏱️  ${solution.flightTime.toFixed(1)} сек`;
      state.infoText = `Заряд: ${charge} | Расстояние: ${Math.round(distance)}м`;
    } else {
      const sign = solution.correction >= 0 ? "+" : "";
      $("resCorr").textContent = `${sign}${solution.correction.toFixed(1)} MIL`;
      $("resCorr").className = "stat-value on";
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
        return 0;
      }
      const value = parseNumber(text);
      if (value === null) throw new InputError(`${title}: введите число`, name);
      return value;
    }

    const charges = B.allowedCharges(DATA, state.weapon);
    const charge = Number(state.charge);
    if (!charges.includes(charge)) throw new InputError("Выберите заряд");

    // Высоты обязательны только при включённой поправке
    const distance = number("distance", "Дистанция до цели", true);
    const gun = number("user_height", "Высота орудия", state.correction);
    const target = number("target_height", "Высота цели", state.correction);
    if (distance <= 0) throw new InputError("Дистанция должна быть больше 0", "distance");
    if (gun < 0) throw new InputError("Высота орудия не может быть отрицательной", "user_height");
    if (target < 0) throw new InputError("Высота цели не может быть отрицательной", "target_height");
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

    let solution;
    try {
      solution = B.solve(DATA, state.weapon, input.charge, input.distance, state.mode,
                         input.gun, input.target, state.correction);
    } catch (e) {
      if (!(e instanceof B.OutOfTableError)) throw e;
      showError(e.title, e.details);
      if (!silent) vibrate([30, 50, 30]);
      return;
    }

    showResult(solution, input.charge, input.distance, !silent);
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
      calculation_mode: state.mode,
      apply_height_correction: state.correction,
    };
  }

  function addHistory(solution, charge, distance) {
    const short = state.weapon === "Миномёт" ? "Мин." : state.weapon;
    let summary = `${short} · з${charge} · ${B.g(distance)} м`;
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
    for (const name of Object.keys(fields)) {
      fields[name].value = String(data[name] ?? "");
      fields[name].closest(".field").classList.remove("error");
    }
    state.mode = data.calculation_mode === "nontable" ? "nontable" : "table";
    modeSeg.update();
    state.correction = Boolean(data.apply_height_correction);
    correctionBox.checked = state.correction;
    updateHeightsDim();
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
    const parts = [String(data.weapon || "Миномёт")];
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
      if (name === "distance") updateChargeHint();
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
  modeSeg.update(true);
  updateHeightsDim();
  updateSavesBadge();
  renderHistory();
  showEmpty();

  // Для отладки и автоматических проверок
  window.App = { state, calculate, applyValues, saves };
})();
