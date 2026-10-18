"""Артиллерийский калькулятор 104-го ДОБ «Волчья стая» (Arma 3, RS:Q)

Модули проекта:
    weapons_data.py — баллистические таблицы (значения не менять)
    ballistics.py   — расчёт возвышения (покрыт тестами в tests/)
    storage.py      — сохранения, настройки, журнал ошибок
    ui_widgets.py   — тема и компоненты интерфейса
    version.py      — номер версии и «Что нового»
    updater.py      — проверка новой версии на GitHub
    Calculator.py   — окно программы (этот файл, точка входа)
"""

import math
import os
import queue
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser

try:
    import winsound
except ImportError:  # Не Windows — вместо писка будет системный сигнал Tk
    winsound = None

import ballistics
import updater
from storage import Store, get_resource_path, log, setup_logging
from version import APP_VERSION, MOBILE_URL, REPOSITORY, WHATS_NEW
from ui_widgets import (
    COLORS, HistoryList, InputField, RoundedButton, RoundedPanel, SegmentedControl, Theme,
    ToggleSwitch, Tween, apply_dark_titlebar, draw_armor_stripes, draw_wolf, enable_dpi_awareness, round_rect,
)
from weapons_data import WEAPON_DATA

MAX_SAVES = 10
MAX_HISTORY = 20
SPLASH_WARNING_S = 5          # Сигнал «скоро разрыв» за 5 секунд, как в артиллерии
UPDATE_CHECK_INTERVAL_S = 24 * 3600


class InputError(ValueError):
    """Ошибка ввода с указанием поля, которое нужно подсветить"""

    def __init__(self, message, field=None):
        super().__init__(message)
        self.field = field


class ArtilleryCalculator:
    # Коды виртуальных клавиш Windows для S и O
    SHORTCUT_KEYCODES = {83: "save", 79: "open"}

    def __init__(self, data_dir=None):
        setup_logging(data_dir)
        enable_dpi_awareness()
        self.root = tk.Tk()
        self.root.title("Артиллерийский калькулятор 104-го ДОБ")
        self.root.configure(bg=COLORS["bg"])
        self.root.report_callback_exception = self._on_tk_error
        self.theme = Theme(self.root)

        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except tk.TclError:
                pass

        # Данные и их проверка (ошибки таблиц пишутся в журнал)
        self.weapon_data = WEAPON_DATA
        self.weapon_index = ballistics.build_index(WEAPON_DATA)
        for problem in ballistics.validate_weapon_data(WEAPON_DATA):
            log.warning("Таблицы: %s", problem)

        self.store = Store(data_dir)
        self.saved_values = self.store.saves
        settings = self.store.settings

        # Переменные (восстанавливаем последнее состояние)
        weapon = settings.get("weapon")
        self.current_weapon = tk.StringVar(value=weapon if weapon in WEAPON_DATA else "Миномёт")
        self.charge_var = tk.StringVar(value=str(settings.get("charge", "0")))
        mode = settings.get("calculation_mode")
        self.calculation_mode = tk.StringVar(value=mode if mode in ("table", "nontable") else "table")
        self.apply_height_correction = tk.BooleanVar(value=bool(settings.get("apply_height_correction", False)))
        self.history = [h for h in settings.get("history", []) if isinstance(h, dict) and "elevation" in h]
        self.result_text = ""
        self.info_text = ""
        self.toast = None
        self.shown_elevation = None
        self.last_solution = None
        # Корректировка огня: исходная дистанция и накопленные сдвиги (м) относительно линии орудие–цель
        self.adjust = None
        self.adjust_step = tk.StringVar(value=str(settings.get("adjust_step", "50")))
        # Таймер полёта
        self.timer_job = None
        self.timer_end = None
        self.timer_warned = False
        self.update_queue = queue.Queue()
        self.update_url = None

        self._setup_geometry(settings.get("geometry"))
        self.setup_ui()
        for field_name in ("distance", "user_height", "target_height"):
            value = settings.get("inputs", {}).get(field_name, "")
            if isinstance(value, str) and value:
                self.entries[field_name].set(value)
        self._update_charge_hint()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        apply_dark_titlebar(self.root, COLORS["bg"])

        # «Что нового» — только для тех, кто уже пользовался прошлой версией
        last_version = settings.get("last_version")
        settings["last_version"] = APP_VERSION
        if settings and last_version != APP_VERSION and ("history" in settings or self.saved_values):
            self.root.after(600, self.show_whats_new)
        self._start_update_check()

    def _setup_geometry(self, saved):
        """Размер окна под двухколоночную раскладку; последнее положение, если оно на экране"""
        px = self.theme.px
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        min_w, min_h = min(screen_w, px(880)), min(screen_h - px(60), px(760))
        self.root.minsize(min_w, min_h)
        try:
            size, x, y = saved.split("+")[0], int(saved.split("+")[1]), int(saved.split("+")[2])
            w, h = (int(v) for v in size.split("x"))
            if w >= min_w and h >= min_h and 0 <= x < screen_w - px(100) and 0 <= y < screen_h - px(100):
                self.root.geometry(f"{w}x{h}+{x}+{y}")
                return
        except (AttributeError, ValueError, IndexError):
            pass
        w = min(screen_w, px(1000))
        h = min(screen_h - px(60), px(820))
        self.root.geometry(f"{w}x{h}+{max(0, (screen_w - w) // 2)}+{max(0, (screen_h - h) // 2 - px(20))}")

    # ------------------------------------------------------------------
    # Ошибки и закрытие
    # ------------------------------------------------------------------

    def _on_tk_error(self, exc_type, exc_value, exc_tb):
        log.error("Необработанная ошибка", exc_info=(exc_type, exc_value, exc_tb))
        try:
            self.show_notification(f"Ошибка: {exc_value}", notification_type="error")
        except tk.TclError:
            pass

    def _on_close(self):
        self._stop_timer()
        self._save_settings()
        self.root.destroy()

    def _save_settings(self):
        if self.root.state() == "normal":
            self.store.settings["geometry"] = self.root.geometry()
        self.store.settings.update({
            "weapon": self.current_weapon.get(),
            "charge": self.charge_var.get(),
            "calculation_mode": self.calculation_mode.get(),
            "apply_height_correction": self.apply_height_correction.get(),
            "inputs": {name: field.get() for name, field in self.entries.items()},
            "history": self.history[:MAX_HISTORY],
            "adjust_step": self.adjust_step.get(),
            "last_version": APP_VERSION,
        })
        self.store.write_settings()

    # ------------------------------------------------------------------
    # Интерфейс
    # ------------------------------------------------------------------

    def setup_ui(self):
        px = self.theme.px
        outer = tk.Frame(self.root, bg=COLORS["bg"])
        outer.pack(fill=tk.BOTH, expand=True, padx=px(24), pady=(px(18), px(24)))

        self._create_header(outer)

        body = tk.Frame(outer, bg=COLORS["bg"])
        body.pack(fill=tk.BOTH, expand=True, pady=(px(18), 0))
        body.columnconfigure(0, weight=11, uniform="col")
        body.columnconfigure(1, weight=9, uniform="col")
        body.rowconfigure(0, weight=1)

        self._create_params_card(body).grid(row=0, column=0, sticky="nsew", padx=(0, px(16)))
        self.result_card = self._create_result_card(body)
        self.result_card.grid(row=0, column=1, sticky="nsew")

        self._on_weapon_change()
        self._on_correction_change()
        self._show_empty_result()
        self.history_list.set_items(self.history)

        # Горячие клавиши (только в главном окне)
        self.root.bind("<Return>", lambda e: self.calculate())
        self.root.bind("<KP_Enter>", lambda e: self.calculate())
        # Ctrl+S / Ctrl+O ловим по коду физической клавиши: <Control-s> не срабатывает
        # при русской раскладке (приходит «ы»/«щ») и при включённом Caps Lock
        self.root.bind("<Control-KeyPress>", self._on_ctrl_shortcut)
        self.root.bind("<F1>", lambda e: self.show_help())
        self.root.bind("<F2>", lambda e: self.toggle_timer())

    def _on_ctrl_shortcut(self, event):
        action = self.SHORTCUT_KEYCODES.get(event.keycode)
        if action is None and event.keysym.lower() in ("s", "o"):
            # Запасной вариант для систем, где keycode отличается от Windows
            action = "save" if event.keysym.lower() == "s" else "open"
        if action == "save":
            self.save_current_values()
            return "break"
        if action == "open":
            self.load_saved_values()
            return "break"
        return None

    def _create_header(self, parent):
        px = self.theme.px
        header = tk.Frame(parent, bg=COLORS["bg"])
        header.pack(fill=tk.X)

        # Логотип: волк «Волчьей стаи» на графитовой плашке, один глаз красный — как у Вульфа
        size = px(52)
        logo = tk.Canvas(header, width=size, height=size, bg=COLORS["bg"], highlightthickness=0, bd=0)
        logo.pack(side=tk.LEFT)
        round_rect(logo, 1, 1, size - 1, size - 1, px(13), fill=COLORS["surface_2"],
                   outline=COLORS["border_strong"])
        draw_wolf(logo, px(7), px(6), size - px(14), COLORS["accent"], COLORS["surface_2"],
                  eye_right=COLORS["error"])

        titles = tk.Frame(header, bg=COLORS["bg"])
        titles.pack(side=tk.LEFT, padx=(px(14), 0))
        tk.Label(titles, text="Артиллерийский калькулятор", font=self.theme.title,
                 fg=COLORS["text"], bg=COLORS["bg"]).pack(anchor="w")
        subtitle = tk.Frame(titles, bg=COLORS["bg"])
        subtitle.pack(anchor="w")
        tk.Label(subtitle, text="104-Й ДОБ  «ВОЛЧЬЯ СТАЯ»", font=self.theme.caption,
                 fg=COLORS["text"], bg=COLORS["bg"]).pack(side=tk.LEFT)
        tk.Label(subtitle, text=f"   ·   ARMA 3   ·   RS:Q   ·   v{APP_VERSION}", font=self.theme.subtitle,
                 fg=COLORS["text_muted"], bg=COLORS["bg"]).pack(side=tk.LEFT)

        self.saves_button = RoundedButton(
            header, self.theme, "", self.load_saved_values, COLORS["bg"],
            variant="secondary", height=38, width=170,
        )
        self.saves_button.pack(side=tk.RIGHT)
        self._update_saves_button()
        RoundedButton(header, self.theme, "?", self.show_help, COLORS["bg"],
                      variant="secondary", height=38, width=38).pack(side=tk.RIGHT, padx=(0, px(8)))
        # Появляется, только если на GitHub есть версия новее
        self.update_button = RoundedButton(header, self.theme, "", self._open_update, COLORS["bg"],
                                           variant="primary", height=38, width=190)

    def _card_title(self, parent, text):
        """Заголовок карточки с маркировкой как на броне 104-го"""
        px = self.theme.px
        frame = tk.Frame(parent, bg=COLORS["surface"])
        stripes = tk.Canvas(frame, width=px(34), height=px(10), bg=COLORS["surface"],
                            highlightthickness=0, bd=0)
        stripes.pack(side=tk.LEFT, padx=(0, px(10)))
        draw_armor_stripes(stripes, 0, 0, px(10), [COLORS["accent"], COLORS["text_muted"], COLORS["text_faint"]],
                           width=px(6), gap=px(2))
        tk.Label(frame, text=text, font=self.theme.body_strong,
                 fg=COLORS["text"], bg=COLORS["surface"]).pack(side=tk.LEFT)
        return frame

    def _caption(self, parent, text, bg=None):
        return tk.Label(parent, text=text.upper(), font=self.theme.caption,
                        fg=COLORS["text_muted"], bg=bg or COLORS["surface"], anchor="w")

    def _create_params_card(self, parent):
        px = self.theme.px
        card = RoundedPanel(parent, self.theme, COLORS["surface"], COLORS["bg"],
                            border=COLORS["border"], padding=22, fill_y=True)
        inner = card.inner
        surface = COLORS["surface"]

        self._card_title(inner, "Параметры стрельбы").pack(anchor="w", pady=(0, px(16)))

        # Орудие
        self._caption(inner, "Орудие").pack(fill=tk.X, pady=(0, px(6)))
        self.weapon_control = SegmentedControl(
            inner, self.theme, self.current_weapon,
            [(name, name) for name in self.weapon_data], surface,
            command=self._on_weapon_change,
        )
        self.weapon_control.pack(fill=tk.X, pady=(0, px(16)))

        # Заряд
        self._caption(inner, "Заряд").pack(fill=tk.X, pady=(0, px(6)))
        self.charge_control = SegmentedControl(
            inner, self.theme, self.charge_var, [], surface,
            command=self._update_charge_hint,
        )
        self.charge_control.pack(fill=tk.X)
        hint_row = tk.Frame(inner, bg=surface)
        hint_row.pack(fill=tk.X, pady=(px(6), px(14)))
        self.charge_hint = tk.Label(hint_row, text="", font=self.theme.small,
                                    fg=COLORS["text_faint"], bg=surface, anchor="w")
        self.charge_hint.pack(side=tk.LEFT)
        self.charge_suggestion = tk.Label(hint_row, text="", font=self.theme.small,
                                          fg=COLORS["text_muted"], bg=surface, anchor="e")
        self.charge_suggestion.pack(side=tk.RIGHT)

        # Поля ввода
        self.entries = {}
        self.entries["distance"] = InputField(inner, self.theme, "Дистанция до цели", surface,
                                              suffix="м", placeholder="например, 1250")
        self.entries["distance"].pack(fill=tk.X, pady=(0, px(14)))
        # Подсказка зарядов обновляется при вводе дистанции (сам расчёт — по Enter/кнопке)
        self.entries["distance"].entry.bind("<KeyRelease>", self._on_distance_key, add="+")

        heights = tk.Frame(inner, bg=surface)
        heights.pack(fill=tk.X, pady=(0, px(16)))
        heights.columnconfigure(0, weight=1, uniform="h")
        heights.columnconfigure(1, weight=1, uniform="h")
        self.entries["user_height"] = InputField(heights, self.theme, "Высота орудия", surface,
                                                 suffix="м", placeholder="0")
        self.entries["user_height"].grid(row=0, column=0, sticky="ew", padx=(0, px(7)))
        self.entries["target_height"] = InputField(heights, self.theme, "Высота цели", surface,
                                                   suffix="м", placeholder="0")
        self.entries["target_height"].grid(row=0, column=1, sticky="ew", padx=(px(7), 0))

        # Режим расчёта
        self._caption(inner, "Режим расчёта").pack(fill=tk.X, pady=(0, px(6)))
        SegmentedControl(
            inner, self.theme, self.calculation_mode,
            [("table", "По таблице"), ("nontable", "Интерполяция")], surface,
        ).pack(fill=tk.X, pady=(0, px(16)))

        # Поправка на высоту
        toggle_row = tk.Frame(inner, bg=surface, cursor="hand2")
        toggle_row.pack(fill=tk.X)
        toggle = ToggleSwitch(toggle_row, self.theme, self.apply_height_correction, surface)
        toggle.pack(side=tk.RIGHT)
        texts = tk.Frame(toggle_row, bg=surface)
        texts.pack(side=tk.LEFT, fill=tk.X, expand=True)
        title = tk.Label(texts, text="Поправка на превышение", font=self.theme.body_strong,
                         fg=COLORS["text"], bg=surface, anchor="w", cursor="hand2")
        title.pack(fill=tk.X)
        subtitle = tk.Label(texts, text="Учитывать разницу высот орудия и цели", font=self.theme.small,
                            fg=COLORS["text_muted"], bg=surface, anchor="w", cursor="hand2")
        subtitle.pack(fill=tk.X)
        for widget in (toggle_row, texts, title, subtitle):
            widget.bind("<Button-1>", lambda e: toggle.toggle())
        self.apply_height_correction.trace_add("write", lambda *args: self._on_correction_change())

        self._create_adjust_panel(inner)
        return card

    def _create_adjust_panel(self, parent):
        """Корректировка огня по докладу наблюдателя (относительно линии орудие–цель)"""
        px = self.theme.px
        surface = COLORS["surface"]
        tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=(px(16), px(14)))

        head = tk.Frame(parent, bg=surface)
        head.pack(fill=tk.X, pady=(0, px(6)))
        self._caption(head, "Корректировка огня").pack(side=tk.LEFT)
        self.adjust_status = tk.Label(head, text="", font=self.theme.small, fg=COLORS["text_muted"], bg=surface)
        self.adjust_status.pack(side=tk.RIGHT)

        buttons = tk.Frame(parent, bg=surface)
        buttons.pack(fill=tk.X)
        actions = [("Недолёт", "short"), ("Перелёт", "over"), ("Левее", "left"), ("Правее", "right")]
        for i, (text, kind) in enumerate(actions):
            buttons.columnconfigure(i, weight=1, uniform="adj")
            RoundedButton(buttons, self.theme, text, lambda k=kind: self.adjust_fire(k), surface,
                          variant="secondary", height=38).grid(
                row=0, column=i, sticky="ew", padx=(0 if i == 0 else px(4), 0 if i == 3 else px(4)))

        row = tk.Frame(parent, bg=surface)
        row.pack(fill=tk.X, pady=(px(8), 0))
        tk.Label(row, text="Шаг", font=self.theme.small, fg=COLORS["text_muted"], bg=surface).pack(side=tk.LEFT)
        self.adjust_field = InputField(row, self.theme, "", surface, suffix="м", height=34)
        self.adjust_field.pack(side=tk.LEFT, padx=(px(8), px(10)))
        self.adjust_field.box.config(width=px(96))
        self.adjust_field.set(self.adjust_step.get())
        self.adjust_field.entry.bind("<KeyRelease>", lambda e: self.adjust_step.set(self.adjust_field.get()), add="+")
        self.adjust_direction = tk.Label(row, text="Недолёт — дальше, перелёт — ближе", font=self.theme.small,
                                         fg=COLORS["text_faint"], bg=surface, anchor="w")
        self.adjust_reset = RoundedButton(row, self.theme, "Сброс", self.reset_adjust, surface,
                                          variant="secondary", height=34, width=72)
        self.adjust_reset.pack(side=tk.RIGHT)
        self.adjust_direction.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _create_result_card(self, parent):
        px = self.theme.px
        card = RoundedPanel(parent, self.theme, COLORS["surface"], COLORS["bg"],
                            border=COLORS["border"], padding=22, fill_y=True)
        inner = card.inner
        surface = COLORS["surface"]

        top = tk.Frame(inner, bg=surface)
        top.pack(fill=tk.X)
        self._card_title(top, "Результат").pack(side=tk.LEFT)
        self.status_pill = tk.Label(top, text="", font=self.theme.caption, padx=px(10), pady=px(2))
        self.status_pill.pack(side=tk.RIGHT)

        # Главное значение — возвышение
        self._caption(inner, "Возвышение").pack(fill=tk.X, pady=(px(20), 0))
        value_row = tk.Frame(inner, bg=surface)
        value_row.pack(fill=tk.X)
        self.res_value = tk.Label(value_row, text="—", font=self.theme.result_big,
                                  fg=COLORS["text_faint"], bg=surface)
        self.res_value.pack(side=tk.LEFT)
        self.res_unit = tk.Label(value_row, text="MIL", font=self.theme.result_unit,
                                 fg=COLORS["text_muted"], bg=surface)
        self.res_unit.pack(side=tk.LEFT, anchor="s", padx=(px(8), 0), pady=(0, px(14)))
        self.value_tween = Tween(self.res_value, self._set_shown_elevation, duration_ms=450, easing="out")

        self.res_message = tk.Label(inner, text="", font=self.theme.body, fg=COLORS["text_muted"],
                                    bg=surface, anchor="w", justify=tk.LEFT)
        self.res_message.pack(fill=tk.X)
        self.res_message.bind("<Configure>", lambda e: self.res_message.config(wraplength=e.width))
        self.res_detail = tk.Label(inner, text="", font=self.theme.small, fg=COLORS["text_faint"],
                                   bg=surface, anchor="w", justify=tk.LEFT)
        self.res_detail.pack(fill=tk.X, pady=(px(2), 0))

        # Сравнение зарядов: по всем, которые дают решение (появляется, если их больше одного)
        self.compare_frame = tk.Frame(inner, bg=surface)
        self.compare_frame.pack(fill=tk.X)

        # Дополнительные показатели
        stats = tk.Frame(inner, bg=surface)
        stats.pack(fill=tk.X, pady=(px(14), 0))
        stats.columnconfigure(0, weight=1, uniform="s")
        stats.columnconfigure(1, weight=1, uniform="s")
        self.stat_time = self._create_stat_tile(stats, "Время полёта")
        self.stat_time.grid(row=0, column=0, sticky="ew", padx=(0, px(6)))
        self.stat_correction = self._create_stat_tile(stats, "Поправка")
        self.stat_correction.grid(row=0, column=1, sticky="ew", padx=(px(6), 0))
        # Клик по плитке времени (или F2) — таймер до разрыва
        for widget in [self.stat_time, self.stat_time.inner] + self.stat_time.inner.winfo_children():
            widget.bind("<Button-1>", lambda e: self.toggle_timer())
            widget.config(cursor="hand2")

        # Кнопки прижаты к низу карточки
        buttons = tk.Frame(inner, bg=surface)
        buttons.pack(side=tk.BOTTOM, fill=tk.X)
        RoundedButton(buttons, self.theme, "Рассчитать", self.calculate, surface,
                      variant="primary", height=50, font=self.theme.button_large).pack(fill=tk.X)
        RoundedButton(buttons, self.theme, "Сохранить как…", self.save_current_values, surface,
                      variant="secondary", height=42).pack(fill=tk.X, pady=(px(10), 0))
        tk.Label(buttons, text="Enter — расчёт   ·   F2 — таймер   ·   Ctrl+S / Ctrl+O   ·   F1 — справка",
                 font=self.theme.small, fg=COLORS["text_faint"], bg=surface).pack(pady=(px(10), 0))

        # Между показателями и кнопками — история расчётов (пока пусто — водяной знак стаи)
        self.history_list = HistoryList(inner, self.theme, surface, self._apply_history, self._clear_history)
        self.history_list.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=(px(14), px(10)))

        return card

    def _create_stat_tile(self, parent, caption):
        px = self.theme.px
        tile = RoundedPanel(parent, self.theme, COLORS["surface_2"], COLORS["surface"],
                            radius=12, padding=14, border=COLORS["border"])
        tk.Label(tile.inner, text=caption.upper(), font=self.theme.caption,
                 fg=COLORS["text_muted"], bg=COLORS["surface_2"], anchor="w").pack(fill=tk.X)
        tile.value = tk.Label(tile.inner, text="—", font=self.theme.stat,
                              fg=COLORS["text"], bg=COLORS["surface_2"], anchor="w")
        tile.value.pack(fill=tk.X, pady=(px(2), 0))
        tile.note = tk.Label(tile.inner, text="", font=self.theme.small,
                             fg=COLORS["text_faint"], bg=COLORS["surface_2"], anchor="w")
        tile.note.pack(fill=tk.X)
        return tile

    # ------------------------------------------------------------------
    # Отображение результата
    # ------------------------------------------------------------------

    def _set_status_pill(self, text, kind):
        colors = {
            "ok": (COLORS["success_soft"], COLORS["success"]),
            "error": (COLORS["error_soft"], COLORS["error"]),
            "idle": (COLORS["surface_2"], COLORS["text_muted"]),
        }
        bg, fg = colors[kind]
        self.status_pill.config(text=text.upper(), bg=bg, fg=fg)

    def _set_shown_elevation(self, value):
        self.res_value.config(text=f"{value:.1f}")

    def _reset_tiles(self):
        self._stop_timer()
        self.last_solution = None
        for tile in (self.stat_time, self.stat_correction):
            tile.value.config(text="—", fg=COLORS["text_faint"])
            tile.note.config(text="")
        self.res_detail.config(text="")
        self._render_comparison([], None)

    def _show_empty_result(self):
        self.value_tween.stop()
        self.shown_elevation = None
        self._set_status_pill("Ожидание", "idle")
        self.res_value.config(text="—", fg=COLORS["text_faint"])
        self.res_unit.config(fg=COLORS["text_faint"])
        self.res_message.config(text="Заполните параметры и нажмите «Рассчитать»", fg=COLORS["text_muted"])
        self._reset_tiles()
        self.result_text = ""
        self.info_text = ""

    def _show_error_result(self, title, details):
        self.value_tween.stop()
        self.shown_elevation = None
        self._set_status_pill("Ошибка", "error")
        self.res_value.config(text="—", fg=COLORS["error"])
        self.res_unit.config(fg=COLORS["text_faint"])
        self.res_message.config(text=f"{title}. {details}", fg=COLORS["error"])
        self._reset_tiles()
        self.result_card.flash(COLORS["error"])
        self.result_text = f"❌ {title}"
        self.info_text = details

    def _show_result(self, solution, charge, distance, animate=True, comparison=()):
        self._stop_timer()
        self.last_solution = solution
        mode = "Таблица" if self.calculation_mode.get() == "table" else "Интерполяция"
        self._set_status_pill(mode, "ok")

        # Число плавно «докручивается» от прошлого значения до нового
        target = solution.elevation
        start = self.shown_elevation if self.shown_elevation is not None else target - 40
        self.res_value.config(fg=COLORS["accent"])
        if animate:
            self.value_tween.start(start, target)
            self.result_card.flash(COLORS["accent"])
        else:
            self._set_shown_elevation(target)
        self.shown_elevation = target

        self.res_unit.config(fg=COLORS["text_muted"])
        message = f"{self.get_current_weapon_name()}  ·  заряд {charge}  ·  {distance:g} м"
        direction = self._adjust_direction_text()
        if direction:
            message += f"  ·  направление {direction}"
        self.res_message.config(text=message, fg=COLORS["text_muted"])
        self._render_comparison(comparison, charge)
        lower, upper = solution.lower_row, solution.upper_row
        if lower is upper:
            self.res_detail.config(text=f"Строка таблицы: {lower['range']} м → {lower['elev']} MIL")
        else:
            self.res_detail.config(
                text=f"Между строками {lower['range']} м → {lower['elev']}  и  {upper['range']} м → {upper['elev']} MIL"
            )

        self.stat_time.value.config(text=f"{solution.flight_time:.1f} с", fg=COLORS["text"])
        self.stat_time.note.config(text="▶ таймер — клик или F2", fg=COLORS["text_faint"])
        if solution.correction is None:
            self.stat_correction.value.config(text="выкл", fg=COLORS["text_faint"])
            self.stat_correction.note.config(text="без учёта высот")
            self.result_text = f"🎯 {target:.1f} MIL | ⏱️  {solution.flight_time:.1f} сек"
            self.info_text = f"Заряд: {charge} | Расстояние: {distance:.0f}м"
        else:
            self.stat_correction.value.config(text=f"{solution.correction:+.1f} MIL", fg=COLORS["text"])
            self.stat_correction.note.config(text=f"база {solution.base_elevation:.1f} MIL")
            self.result_text = f"✈️  {target:.1f} MIL | ⏱️  {solution.flight_time:.1f} сек"
            self.info_text = (f"Базовое: {solution.base_elevation:.1f} MIL | "
                              f"Поправка на высоту: {solution.correction:+.1f} MIL")

    # ------------------------------------------------------------------
    # Реакция на изменения параметров
    # ------------------------------------------------------------------

    def _on_weapon_change(self):
        charges = self.get_current_weapon_allowed_charges()
        self.charge_control.set_options([(str(c), str(c)) for c in charges])
        if self.charge_var.get() not in [str(c) for c in charges]:
            self.charge_var.set(str(charges[0]) if charges else "")
        self._update_charge_hint()

    def _on_correction_change(self):
        # Высоты нужны только при включённой поправке — иначе поля приглушены
        dimmed = not self.apply_height_correction.get()
        for name in ("user_height", "target_height"):
            self.entries[name].set_dimmed(dimmed)

    def _current_distance(self):
        """Дистанция из поля или None, если там не число"""
        text = self.entries["distance"].get().strip().replace(",", ".")
        try:
            value = float(text)
        except ValueError:
            return None
        return value if math.isfinite(value) and value > 0 else None

    def _update_charge_hint(self):
        weapon = self.get_current_weapon_name()
        try:
            rows = ballistics.charge_rows(self.weapon_data, weapon, int(self.charge_var.get()))
        except ValueError:
            rows = []
        span = ballistics.charge_range(rows)
        if span:
            text = f"Дальность {span[0]} – {span[1]} м"
            if span[2]:
                text += f"   ·   шаг {span[2]} м"
            self.charge_hint.config(text=text)
        else:
            self.charge_hint.config(text="")

        # Какие заряды достают до введённой дистанции
        distance = self._current_distance()
        if distance is None:
            self.charge_control.set_suggested(None)
            self.charge_suggestion.config(text="")
            return
        suitable = ballistics.charges_for_distance(self.weapon_data, weapon, distance)
        self.charge_control.set_suggested(suitable)
        if not suitable:
            self.charge_suggestion.config(text="Ни один заряд не достаёт", fg=COLORS["error"])
        elif self.charge_var.get() in [str(c) for c in suitable]:
            self.charge_suggestion.config(text="Заряд подходит", fg=COLORS["text_muted"])
        else:
            listed = ", ".join(str(c) for c in suitable)
            self.charge_suggestion.config(text=f"Подходят: {listed}", fg=COLORS["text"])

    def _update_saves_button(self):
        count = len(self.saved_values)
        self.saves_button.set_text(f"Сохранения  {count}/{MAX_SAVES}" if count else "Сохранения")

    # ------------------------------------------------------------------
    # История расчётов
    # ------------------------------------------------------------------

    def _snapshot(self):
        """Текущие параметры в виде словаря (для истории и сохранений)"""
        return {
            "distance": self.entries["distance"].get(),
            "charge": self.charge_var.get(),
            "user_height": self.entries["user_height"].get(),
            "target_height": self.entries["target_height"].get(),
            "weapon": self.get_current_weapon_name(),
            "calculation_mode": self.calculation_mode.get(),
            "apply_height_correction": self.apply_height_correction.get(),
        }

    def _add_history(self, solution, charge, distance):
        weapon_short = "Мин." if self.get_current_weapon_name() == "Миномёт" else self.get_current_weapon_name()
        summary = f"{weapon_short} · з{charge} · {distance:g} м"
        if solution.correction is not None:
            # Разница высот — чтобы отличать расчёты одной дистанции с поправкой и без
            heights = self._snapshot()
            try:
                diff = float(heights["target_height"].replace(",", ".") or 0) - \
                    float(heights["user_height"].replace(",", ".") or 0)
                summary += f" · Δh {diff:+g}"
            except ValueError:
                pass
        entry = dict(self._snapshot(),
                     elevation=round(solution.elevation, 1),
                     time=time.strftime("%H:%M"),
                     summary=summary)
        # Повтор того же расчёта не дублируем — поднимаем наверх
        key = lambda h: (h.get("weapon"), h.get("charge"), h.get("distance"), h.get("elevation"))
        self.history = [entry] + [h for h in self.history if key(h) != key(entry)][:MAX_HISTORY - 1]
        self.history_list.set_items(self.history)

    def _apply_history(self, item):
        self._apply_values(item)
        self.calculate(silent=True)

    def _clear_history(self):
        if self._confirm("Очистить историю?", "Список последних расчётов будет удалён.", "Очистить", danger=True):
            self.history = []
            self.history_list.set_items(self.history)

    # ------------------------------------------------------------------
    # Уведомления и диалоги
    # ------------------------------------------------------------------

    def show_notification(self, message, duration=2200, notification_type="info"):
        """Всплывающее уведомление внизу окна

        notification_type: "info", "success", "error"
        """
        px = self.theme.px
        dot_colors = {"info": COLORS["accent"], "success": COLORS["success"], "error": COLORS["error"]}
        dot_color = dot_colors.get(notification_type, COLORS["accent"])

        if self.toast is not None:
            try:
                self.toast.destroy()
            except tk.TclError:
                pass

        popup = tk.Toplevel(self.root)
        self.toast = popup
        popup.withdraw()
        popup.wm_overrideredirect(True)
        key = COLORS["transparent"]
        popup.configure(bg=key)
        try:
            popup.attributes("-transparentcolor", key)
        except tk.TclError:
            pass

        font = tkfont.Font(root=self.root, font=self.theme.body_strong)
        width = font.measure(message) + px(64)
        height = px(46)
        canvas = tk.Canvas(popup, width=width, height=height, bg=key, highlightthickness=0, bd=0)
        canvas.pack()
        round_rect(canvas, 1, 1, width - 1, height - 1, px(12),
                   fill=COLORS["surface_3"], outline=COLORS["border_strong"])
        cy = height / 2
        canvas.create_oval(px(18), cy - px(5), px(28), cy + px(5), fill=dot_color, outline="")
        canvas.create_text(px(40), cy, text=message, anchor="w", font=self.theme.body_strong,
                           fill=COLORS["text"])

        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + self.root.winfo_height() - height - px(40)
        popup.geometry(f"{width}x{height}+{x}+{y}")
        popup.attributes("-topmost", True)
        try:
            popup.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        popup.deiconify()

        def set_alpha(value):
            popup.attributes("-alpha", value)

        fade = Tween(popup, set_alpha, duration_ms=160, easing="out")
        fade.start(0.0, 1.0)

        def fade_out():
            out = Tween(popup, set_alpha, duration_ms=220, easing="out")
            out.start(1.0, 0.0)
            popup.after(240, lambda: popup.winfo_exists() and popup.destroy())

        popup.after(duration, fade_out)

    def _make_dialog(self, title):
        """Тёмное модальное окно поверх главного"""
        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.title(title)
        dialog.configure(bg=COLORS["surface"])
        dialog.resizable(False, False)
        dialog.transient(self.root)
        icon_path = get_resource_path("icon.ico")
        if os.path.exists(icon_path):
            try:
                dialog.iconbitmap(icon_path)
            except tk.TclError:
                pass
        return dialog

    def _show_dialog(self, dialog, focus_widget=None):
        """Центрировать, показать и дождаться закрытия диалога"""
        dialog.update_idletasks()
        w, h = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 3
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        dialog.deiconify()
        apply_dark_titlebar(dialog, COLORS["surface"])
        dialog.grab_set()
        (focus_widget or dialog).focus_set()
        dialog.wait_window()

    def _dialog_buttons(self, parent, confirm_text, on_confirm, on_cancel, variant="primary"):
        px = self.theme.px
        row = tk.Frame(parent, bg=COLORS["surface"])
        row.pack(fill=tk.X, pady=(px(20), 0))
        row.columnconfigure(0, weight=1, uniform="b")
        row.columnconfigure(1, weight=1, uniform="b")
        RoundedButton(row, self.theme, "Отмена", on_cancel, COLORS["surface"],
                      variant="secondary", height=40).grid(row=0, column=0, sticky="ew", padx=(0, px(6)))
        RoundedButton(row, self.theme, confirm_text, on_confirm, COLORS["surface"],
                      variant=variant, height=40).grid(row=0, column=1, sticky="ew", padx=(px(6), 0))

    def _ask_string(self, title, label, initial=""):
        """Диалог ввода строки. Возвращает строку или None"""
        px = self.theme.px
        dialog = self._make_dialog(title)
        body = tk.Frame(dialog, bg=COLORS["surface"], width=px(380))
        body.pack(padx=px(24), pady=px(22))
        tk.Label(body, text=title, font=self.theme.title, fg=COLORS["text"],
                 bg=COLORS["surface"]).pack(anchor="w", pady=(0, px(14)))
        field = InputField(body, self.theme, label, COLORS["surface"], numeric=False)
        field.pack(fill=tk.X)
        field.box.config(width=px(360))
        field.set(initial)
        result = [None]

        def confirm():
            result[0] = field.get()
            dialog.destroy()

        self._dialog_buttons(body, "Сохранить", confirm, dialog.destroy)
        dialog.bind("<Return>", lambda e: confirm())
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        self._show_dialog(dialog, field.entry)
        return result[0]

    def _confirm(self, title, message, confirm_text, danger=False):
        """Диалог подтверждения. Возвращает True/False"""
        px = self.theme.px
        dialog = self._make_dialog(title)
        body = tk.Frame(dialog, bg=COLORS["surface"])
        body.pack(padx=px(24), pady=px(22))
        tk.Label(body, text=title, font=self.theme.title, fg=COLORS["text"],
                 bg=COLORS["surface"]).pack(anchor="w")
        tk.Label(body, text=message, font=self.theme.body, fg=COLORS["text_muted"],
                 bg=COLORS["surface"], wraplength=px(340), justify=tk.LEFT).pack(anchor="w", pady=(px(6), 0))
        tk.Frame(body, bg=COLORS["surface"], width=px(340), height=1).pack()
        result = [False]

        def confirm():
            result[0] = True
            dialog.destroy()

        self._dialog_buttons(body, confirm_text, confirm, dialog.destroy,
                             variant="danger" if danger else "primary")
        dialog.bind("<Return>", lambda e: confirm())
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        self._show_dialog(dialog)
        return result[0]

    # ------------------------------------------------------------------
    # Сохранения
    # ------------------------------------------------------------------

    def save_to_file(self):
        """Сохранить значения в файл. Возвращает True при успехе."""
        if self.store.write_saves():
            return True
        self.show_notification("Не удалось записать файл сохранений", notification_type="error")
        return False

    def save_current_values(self):
        """Сохранить текущие значения с именем"""
        name = self._ask_string("Сохранить значения", "Название")
        if name is None:
            return
        name = name.strip()
        if not name:
            return

        # Лимит касается только новых имён — перезапись существующего разрешена
        if name not in self.saved_values and len(self.saved_values) >= MAX_SAVES:
            self.show_notification(f"Максимум {MAX_SAVES} сохранений", notification_type="error")
            return

        if name in self.saved_values and not self._confirm(
                "Перезаписать?", f"Сохранение «{name}» уже существует и будет заменено.", "Перезаписать"):
            return

        self.saved_values[name] = dict(self._snapshot(), result=self.result_text, info=self.info_text)
        if self.save_to_file():
            self._update_saves_button()
            self.show_notification(f"Сохранено «{name}»", notification_type="success")

    def _describe_save(self, data):
        parts = [str(data.get("weapon", "Миномёт"))]
        if str(data.get("charge", "")).strip():
            parts.append(f"заряд {data.get('charge')}")
        if str(data.get("distance", "")).strip():
            parts.append(f"{data.get('distance')} м")
        return "  ·  ".join(parts)

    def load_saved_values(self):
        """Окно со списком сохранений"""
        if not self.saved_values:
            self.show_notification("Нет сохранённых значений", notification_type="error")
            return

        px = self.theme.px
        dialog = self._make_dialog("Сохранения")
        body = tk.Frame(dialog, bg=COLORS["surface"])
        body.pack(padx=px(24), pady=px(22))
        tk.Label(body, text="Сохранения", font=self.theme.title, fg=COLORS["text"],
                 bg=COLORS["surface"]).pack(anchor="w")
        tk.Label(body, text="Двойной щелчок — загрузить   ·   ↑/↓ — выбор", font=self.theme.small,
                 fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, px(14)))

        list_frame = tk.Frame(body, bg=COLORS["surface"])
        list_frame.pack(fill=tk.X)
        tk.Frame(body, bg=COLORS["surface"], width=px(400), height=1).pack()

        selected = {"name": None}
        rows = {}

        def paint(name):
            row = rows[name]
            active = name == selected["name"]
            row.fill_color = COLORS["surface_3"] if active else COLORS["surface_2"]
            row.border = row.base_border = COLORS["accent"] if active else COLORS["border"]
            for widget in [row.inner] + row.inner.winfo_children():
                widget.config(bg=row.fill_color)
            row._redraw()

        def select(name):
            previous = selected["name"]
            selected["name"] = name
            if previous in rows:
                paint(previous)
            paint(name)

        def move(delta):
            names = list(rows)
            if not names:
                return
            current = names.index(selected["name"]) if selected["name"] in names else -1
            select(names[max(0, min(len(names) - 1, current + delta))])

        def load_selected(event=None):
            name = selected["name"]
            if name is None:
                self.show_notification("Выберите сохранение", notification_type="error")
                return
            dialog.destroy()
            self._apply_save(name)

        def delete_selected():
            name = selected["name"]
            if name is None:
                self.show_notification("Выберите сохранение для удаления", notification_type="error")
                return
            dialog.grab_release()
            confirmed = self._confirm("Удалить сохранение?", f"«{name}» будет удалено без возможности восстановления.",
                                      "Удалить", danger=True)
            if not dialog.winfo_exists():
                return
            dialog.grab_set()
            if not confirmed:
                return
            del self.saved_values[name]
            self.save_to_file()
            self._update_saves_button()
            rows.pop(name).destroy()
            selected["name"] = None
            self.show_notification(f"Сохранение «{name}» удалено", notification_type="success")
            if not self.saved_values:
                dialog.destroy()

        for name, data in self.saved_values.items():
            row = RoundedPanel(list_frame, self.theme, COLORS["surface_2"], COLORS["surface"],
                               radius=10, padding=12, border=COLORS["border"])
            row.pack(fill=tk.X, pady=(0, px(8)))
            row.config(cursor="hand2")
            tk.Label(row.inner, text=name, font=self.theme.body_strong, fg=COLORS["text"],
                     bg=COLORS["surface_2"], anchor="w").pack(fill=tk.X)
            tk.Label(row.inner, text=self._describe_save(data), font=self.theme.small,
                     fg=COLORS["text_muted"], bg=COLORS["surface_2"], anchor="w").pack(fill=tk.X)
            rows[name] = row
            for widget in [row, row.inner] + row.inner.winfo_children():
                widget.bind("<Button-1>", lambda e, n=name: select(n))
                widget.bind("<Double-Button-1>", lambda e, n=name: (select(n), load_selected()))

        buttons = tk.Frame(body, bg=COLORS["surface"])
        buttons.pack(fill=tk.X, pady=(px(12), 0))
        buttons.columnconfigure(0, weight=1, uniform="b")
        buttons.columnconfigure(1, weight=1, uniform="b")
        RoundedButton(buttons, self.theme, "Удалить", delete_selected, COLORS["surface"],
                      variant="danger", height=40).grid(row=0, column=0, sticky="ew", padx=(0, px(6)))
        RoundedButton(buttons, self.theme, "Загрузить", load_selected, COLORS["surface"],
                      variant="primary", height=40).grid(row=0, column=1, sticky="ew", padx=(px(6), 0))

        dialog.bind("<Return>", load_selected)
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.bind("<Up>", lambda e: move(-1))
        dialog.bind("<Down>", lambda e: move(1))
        dialog.bind("<Delete>", lambda e: delete_selected())
        move(1)  # Сразу выбрать первое сохранение
        self._show_dialog(dialog)

    def _apply_values(self, data):
        """Подставить параметры из словаря (сохранение или запись истории)"""
        saved_weapon = data.get("weapon", "Миномёт")
        if saved_weapon not in self.weapon_data:
            saved_weapon = "Миномёт"
        self.current_weapon.set(saved_weapon)
        self._on_weapon_change()
        charge = str(data.get("charge", "")).strip()
        if charge in [str(c) for c in self.get_current_weapon_allowed_charges()]:
            self.charge_var.set(charge)

        for field_name in ("distance", "user_height", "target_height"):
            self.entries[field_name].set(str(data.get(field_name, "")))

        mode = data.get("calculation_mode", "table")
        self.calculation_mode.set(mode if mode in ("table", "nontable") else "table")
        self.apply_height_correction.set(bool(data.get("apply_height_correction", False)))
        self._update_charge_hint()

    def _apply_save(self, name):
        """Подставить значения из сохранения и пересчитать результат"""
        self._apply_values(self.saved_values[name])
        self.calculate(silent=True)
        self.show_notification(f"Загружено «{name}»", notification_type="success")

    # ------------------------------------------------------------------
    # Данные орудий
    # ------------------------------------------------------------------

    def get_current_weapon_name(self):
        return self.current_weapon.get()

    def get_current_weapon_allowed_charges(self):
        return ballistics.allowed_charges(self.weapon_data, self.get_current_weapon_name())

    # ------------------------------------------------------------------
    # Расчёт
    # ------------------------------------------------------------------

    def _validate_inputs(self):
        """Валидация входных данных перед расчётом

        Возвращает кортеж (distance, charge, user_height, target_height).
        При ошибке бросает InputError с понятным сообщением и именем поля.
        """
        def parse_number(field_name, field_title, required=True, default=0.0):
            text = self.entries[field_name].get().strip()
            if not text:
                if required:
                    raise InputError(f"Заполните поле «{field_title}»", field_name)
                return default
            try:
                # Разрешаем запятую как десятичный разделитель
                value = float(text.replace(",", "."))
            except ValueError:
                raise InputError(f"{field_title}: введите число", field_name) from None
            if not math.isfinite(value):
                raise InputError(f"{field_title}: введите число", field_name)
            return value

        allowed_charges = self.get_current_weapon_allowed_charges()
        if not allowed_charges:
            raise InputError("Для выбранного орудия нет данных зарядов")
        try:
            charge = int(self.charge_var.get())
        except ValueError:
            raise InputError("Выберите заряд") from None
        if charge not in allowed_charges:
            raise InputError(f"Заряд должен быть одним из: {', '.join(map(str, allowed_charges))}")

        # Высоты обязательны только при включённой поправке
        heights_required = self.apply_height_correction.get()
        distance = parse_number("distance", "Дистанция до цели")
        user_height = parse_number("user_height", "Высота орудия", heights_required)
        target_height = parse_number("target_height", "Высота цели", heights_required)

        if distance <= 0:
            raise InputError("Дистанция должна быть больше 0", "distance")
        if user_height < 0:
            raise InputError("Высота орудия не может быть отрицательной", "user_height")
        if target_height < 0:
            raise InputError("Высота цели не может быть отрицательной", "target_height")

        return distance, charge, user_height, target_height

    def calculate(self, silent=False):
        """Основная функция расчета

        silent=True — без уведомлений об ошибках ввода и без анимации (загрузка сохранения/истории)
        """
        try:
            distance, charge, user_height, target_height = self._validate_inputs()
        except InputError as e:
            if silent:
                self._show_empty_result()
            else:
                if e.field:
                    self.entries[e.field].mark_error()
                self.show_notification(str(e), notification_type="error")
            return

        try:
            solution = ballistics.solve(
                self.weapon_data, self.weapon_index, self.get_current_weapon_name(), charge, distance,
                self.calculation_mode.get(), user_height, target_height, self.apply_height_correction.get(),
            )
        except ballistics.OutOfTableError as e:
            self._show_error_result(e.title, e.details)
            return

        comparison = ballistics.compare_charges(
            self.weapon_data, self.weapon_index, self.get_current_weapon_name(), distance,
            self.calculation_mode.get(), user_height, target_height, self.apply_height_correction.get(),
        )
        self._show_result(solution, charge, distance, animate=not silent, comparison=comparison)
        self._add_history(solution, charge, distance)

    # ------------------------------------------------------------------
    # Сравнение зарядов
    # ------------------------------------------------------------------

    def _render_comparison(self, comparison, current_charge):
        """Плашки «заряд · возвышение · время» по всем подходящим зарядам; клик — выбрать заряд"""
        for child in self.compare_frame.winfo_children():
            child.destroy()
        if len(comparison) < 2:
            return
        px = self.theme.px
        surface = COLORS["surface"]
        # Правило из методички: меньший заряд — снаряд летит быстрее, противник успевает меньше
        fastest = min(comparison, key=lambda item: item[1].flight_time)[0]
        row = tk.Frame(self.compare_frame, bg=surface)
        row.pack(fill=tk.X, pady=(px(10), 0))
        self._caption(row, "Заряды").pack(side=tk.LEFT, padx=(0, px(8)))
        font = tkfont.Font(root=self.root, font=self.theme.small)
        for charge, solution in comparison:
            text = f"з{charge}   {solution.elevation:.1f}   {solution.flight_time:.0f} с"
            if charge == fastest:
                text += "   быстрее"
            active = charge == current_charge
            w, h = font.measure(text) + px(20), px(26)
            chip = tk.Canvas(row, width=w, height=h, bg=surface, highlightthickness=0, bd=0, cursor="hand2")
            chip.pack(side=tk.LEFT, padx=(0, px(6)))
            round_rect(chip, 1, 1, w - 1, h - 1, px(7),
                       fill=COLORS["surface_3"] if active else COLORS["surface_2"],
                       outline=COLORS["accent"] if active else COLORS["border"])
            chip.create_text(w / 2, h / 2, text=text, font=self.theme.small,
                             fill=COLORS["text"] if active else COLORS["text_muted"])
            chip.bind("<Button-1>", lambda e, c=charge: self._select_charge(c))

    def _select_charge(self, charge):
        self.charge_var.set(str(charge))
        self._update_charge_hint()
        self.calculate()

    # ------------------------------------------------------------------
    # Корректировка огня
    # ------------------------------------------------------------------

    def adjust_fire(self, kind):
        """Недолёт → дальше, перелёт → ближе, левее/правее — сместить разрыв вбок на шаг"""
        try:
            step = float(self.adjust_field.get().strip().replace(",", "."))
            if not math.isfinite(step) or step <= 0:
                raise ValueError
        except ValueError:
            self.adjust_field.mark_error()
            self.show_notification("Шаг корректировки: введите число больше 0", notification_type="error")
            return
        if self.adjust is None:
            base = self._current_distance()
            if base is None:
                self.entries["distance"].mark_error()
                self.show_notification("Сначала введите дистанцию до цели", notification_type="error")
                return
            self.adjust = {"base": base, "along": 0.0, "lateral": 0.0}
        key, sign = {"short": ("along", 1), "over": ("along", -1), "left": ("lateral", -1),
                     "right": ("lateral", 1)}[kind]
        self.adjust[key] += sign * step

        distance, _ = ballistics.adjust_fire(self.adjust["base"], self.adjust["along"], self.adjust["lateral"])
        distance = round(distance, 1)
        self.entries["distance"].set(f"{distance:g}")
        # Дистанция после корректировки почти никогда не совпадает со строкой таблицы
        if self.calculation_mode.get() == "table" and \
                ballistics.table_lookup(self.weapon_index, self.get_current_weapon_name(),
                                        int(self.charge_var.get() or 0), distance) is None:
            self.calculation_mode.set("nontable")
            self.show_notification("Режим переключён на интерполяцию")
        self._update_adjust_status()
        self._update_charge_hint()
        self.calculate()

    def reset_adjust(self):
        if self.adjust is None:
            return
        self.entries["distance"].set(f"{self.adjust['base']:g}")
        self.adjust = None
        self._update_adjust_status()
        self._update_charge_hint()
        self.calculate(silent=True)

    def _adjust_direction_text(self):
        if not self.adjust or not self.adjust["lateral"]:
            return ""
        _, direction = ballistics.adjust_fire(self.adjust["base"], self.adjust["along"], self.adjust["lateral"])
        return f"{abs(direction):.1f} MIL {'вправо' if direction > 0 else 'влево'}"

    def _update_adjust_status(self):
        if not self.adjust:
            self.adjust_status.config(text="")
            self.adjust_direction.config(text="Недолёт — дальше, перелёт — ближе", fg=COLORS["text_faint"])
            return
        parts = []
        if self.adjust["along"]:
            parts.append(f"{abs(self.adjust['along']):g} м {'дальше' if self.adjust['along'] > 0 else 'ближе'}")
        if self.adjust["lateral"]:
            parts.append(f"{abs(self.adjust['lateral']):g} м {'правее' if self.adjust['lateral'] > 0 else 'левее'}")
        self.adjust_status.config(text=" · ".join(parts) or "без сдвига")
        # Короткая запись, чтобы влезала рядом с полем шага: + вправо, − влево
        _, mils = ballistics.adjust_fire(self.adjust["base"], self.adjust["along"], self.adjust["lateral"])
        text = f"Направление {'+' if mils > 0 else '−'}{abs(mils):.1f} MIL" if self.adjust["lateral"] \
            else "Направление без изменений"
        self.adjust_direction.config(text=text, fg=COLORS["text"] if self.adjust["lateral"] else COLORS["text_muted"])

    def _on_distance_key(self, event):
        # Enter, Tab и стрелки не меняют число — корректировку не сбрасываем
        if event.keysym in ("Return", "KP_Enter", "Tab", "Left", "Right", "Up", "Down", "Home", "End",
                            "Shift_L", "Shift_R", "Control_L", "Control_R", "F1", "F2"):
            return
        self._on_distance_typed()

    def _on_distance_typed(self):
        # Дистанцию изменили вручную — прежняя корректировка больше не относится к ней
        if self.adjust is not None:
            self.adjust = None
            self._update_adjust_status()
        self._update_charge_hint()

    # ------------------------------------------------------------------
    # Таймер полёта
    # ------------------------------------------------------------------

    def toggle_timer(self):
        if self.timer_job is not None:
            self._stop_timer()
            self._show_flight_time()
            return
        if self.last_solution is None:
            self.show_notification("Сначала выполните расчёт", notification_type="error")
            return
        self.timer_end = time.perf_counter() + self.last_solution.flight_time
        self.timer_warned = False
        self.stat_time.base_border = self.stat_time.border = COLORS["accent"]
        self.stat_time._redraw()
        self._beep(1200, 80)
        self._timer_tick()

    def _timer_tick(self):
        remaining = self.timer_end - time.perf_counter()
        if remaining <= 0:
            self._stop_timer()
            self._beep(900, 600)
            self.show_notification("Разрыв!", notification_type="success")
            self.stat_time.flash(COLORS["accent"])
            self._show_flight_time()
            return
        if remaining <= SPLASH_WARNING_S and not self.timer_warned:
            self.timer_warned = True
            self._beep(1500, 150)
        warn = remaining <= SPLASH_WARNING_S
        self.stat_time.value.config(text=f"{remaining:.1f} с", fg=COLORS["accent"] if warn else COLORS["text"])
        self.stat_time.note.config(text="скоро разрыв!" if warn else "до разрыва · F2 — стоп",
                                   fg=COLORS["accent"] if warn else COLORS["text_muted"])
        self.timer_job = self.root.after(50, self._timer_tick)

    def _stop_timer(self):
        if self.timer_job is not None:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None
        if hasattr(self, "stat_time"):
            self.stat_time.base_border = self.stat_time.border = COLORS["border"]
            self.stat_time._redraw()

    def _show_flight_time(self):
        if self.last_solution is not None:
            self.stat_time.value.config(text=f"{self.last_solution.flight_time:.1f} с", fg=COLORS["text"])
            self.stat_time.note.config(text="▶ таймер — клик или F2", fg=COLORS["text_faint"])

    def _beep(self, frequency, duration_ms):
        """Звуковой сигнал без подвисания окна (winsound.Beep блокирует — запускаем в потоке)"""
        if winsound is not None:
            threading.Thread(target=winsound.Beep, args=(frequency, duration_ms), daemon=True).start()
        else:
            self.root.bell()

    # ------------------------------------------------------------------
    # Справка, «Что нового», обновления
    # ------------------------------------------------------------------

    HELP_SECTIONS = [
        ("Порядок расчёта",
         "Выберите орудие и заряд, введите дистанцию до цели и нажмите «Рассчитать» (Enter). "
         "Заряды, которые не достают до цели, приглушены. Методичка советует брать меньший заряд — "
         "снаряд летит быстрее; в строке «Заряды» самый быстрый помечен."),
        ("Режимы",
         "«По таблице» — только дальности из таблицы (шаг 50 или 100 м). «Интерполяция» — любая "
         "дальность внутри диапазона заряда: значение берётся между двумя соседними строками таблицы."),
        ("Поправка на превышение",
         "Учитывает разницу высот орудия и цели (высоты — с карты, над уровнем моря). Цель выше — "
         "возвышение уменьшается, ниже — увеличивается. Методичка: желательно от 50 м разницы, "
         "обязательно от 100 м."),
        ("Корректировка огня",
         "После выстрела по докладу наблюдателя: «Недолёт» — дальше на шаг, «Перелёт» — ближе, "
         "«Левее» / «Правее» — сместить разрыв вбок. Сдвиги считаются относительно линии орудие–цель; "
         "дистанция пересчитывается, а поправку направления (в милах, 6400 в круге) нужно внести в азимут. "
         "«Сброс» возвращает исходную дистанцию."),
        ("Таймер полёта",
         "Клик по плитке «Время полёта» или F2 — обратный отсчёт до разрыва. Короткий сигнал за "
         "5 секунд, длинный — в момент разрыва. Повторное нажатие останавливает таймер."),
        ("Клавиши",
         "Enter — расчёт · F2 — таймер · F1 — справка · Ctrl+S — сохранить · Ctrl+O — сохранения · "
         "Tab — по элементам · ←/→ — переключатели · пробел — тумблер и кнопки."),
    ]

    def show_help(self):
        px = self.theme.px
        dialog = self._make_dialog("Справка")
        body = tk.Frame(dialog, bg=COLORS["surface"])
        body.pack(padx=px(26), pady=px(22))
        tk.Label(body, text="Справка", font=self.theme.title, fg=COLORS["text"],
                 bg=COLORS["surface"]).pack(anchor="w")
        tk.Label(body, text=f"Артиллерийский калькулятор 104-го ДОБ · версия {APP_VERSION}", font=self.theme.small,
                 fg=COLORS["text_muted"], bg=COLORS["surface"]).pack(anchor="w", pady=(0, px(10)))
        for title, text in self.HELP_SECTIONS:
            self._caption(body, title).pack(fill=tk.X, pady=(px(10), px(3)))
            tk.Label(body, text=text, font=self.theme.body, fg=COLORS["text"], bg=COLORS["surface"],
                     wraplength=px(540), justify=tk.LEFT, anchor="w").pack(fill=tk.X)
        links = tk.Frame(body, bg=COLORS["surface"])
        links.pack(fill=tk.X, pady=(px(14), 0))
        for text, url in (("Проект на GitHub", f"https://github.com/{REPOSITORY}"),
                          ("Версия для телефона", MOBILE_URL)):
            link = tk.Label(links, text=text, font=self.theme.body_strong, fg=COLORS["accent"],
                            bg=COLORS["surface"], cursor="hand2")
            link.pack(side=tk.LEFT, padx=(0, px(18)))
            link.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
        row = tk.Frame(body, bg=COLORS["surface"])
        row.pack(fill=tk.X, pady=(px(18), 0))
        RoundedButton(row, self.theme, "Что нового", lambda: (dialog.destroy(), self.show_whats_new()),
                      COLORS["surface"], variant="secondary", height=40, width=150).pack(side=tk.LEFT)
        RoundedButton(row, self.theme, "Закрыть", dialog.destroy, COLORS["surface"],
                      variant="primary", height=40, width=150).pack(side=tk.RIGHT)
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.bind("<Return>", lambda e: dialog.destroy())
        self._show_dialog(dialog)

    def show_whats_new(self):
        px = self.theme.px
        dialog = self._make_dialog("Что нового")
        body = tk.Frame(dialog, bg=COLORS["surface"])
        body.pack(padx=px(26), pady=px(22))
        tk.Label(body, text=f"Что нового в версии {APP_VERSION}", font=self.theme.title, fg=COLORS["text"],
                 bg=COLORS["surface"]).pack(anchor="w", pady=(0, px(10)))
        for item in WHATS_NEW.get(APP_VERSION, []):
            line = tk.Frame(body, bg=COLORS["surface"])
            line.pack(fill=tk.X, pady=(px(4), 0))
            tk.Label(line, text="—", font=self.theme.body, fg=COLORS["text_faint"],
                     bg=COLORS["surface"]).pack(side=tk.LEFT, anchor="n", padx=(0, px(8)))
            tk.Label(line, text=item, font=self.theme.body, fg=COLORS["text"], bg=COLORS["surface"],
                     wraplength=px(480), justify=tk.LEFT, anchor="w").pack(side=tk.LEFT, fill=tk.X)
        RoundedButton(body, self.theme, "Понятно", dialog.destroy, COLORS["surface"],
                      variant="primary", height=40).pack(fill=tk.X, pady=(px(18), 0))
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.bind("<Return>", lambda e: dialog.destroy())
        self._show_dialog(dialog)

    def _start_update_check(self):
        """Проверка новой версии на GitHub в фоне — не чаще раза в сутки"""
        settings = self.store.settings
        known = settings.get("update_available")
        if isinstance(known, dict) and updater.is_newer(known.get("tag", "")):
            self._show_update(known["tag"], known.get("url"))
        if time.time() - float(settings.get("last_update_check", 0) or 0) < UPDATE_CHECK_INTERVAL_S:
            return

        def worker():
            self.update_queue.put(updater.check_for_update())

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(500, self._poll_update)

    def _poll_update(self):
        try:
            result = self.update_queue.get_nowait()
        except queue.Empty:
            self.root.after(500, self._poll_update)
            return
        self.store.settings["last_update_check"] = time.time()
        if result:
            tag, url = result
            self.store.settings["update_available"] = {"tag": tag, "url": url}
            self._show_update(tag, url)
            self.show_notification(f"Доступна новая версия {tag}")
        else:
            self.store.settings.pop("update_available", None)

    def _show_update(self, tag, url):
        self.update_url = url or f"https://github.com/{REPOSITORY}/releases/latest"
        self.update_button.set_text(f"Обновление {tag}")
        if not self.update_button.winfo_ismapped():
            self.update_button.pack(side=tk.RIGHT, padx=(0, self.theme.px(8)))

    def _open_update(self):
        if self.update_url:
            webbrowser.open(self.update_url)

    def run(self):
        self.root.mainloop()


def main():
    setup_logging()

    def log_uncaught(exc_type, exc_value, exc_tb):
        log.critical("Аварийное завершение", exc_info=(exc_type, exc_value, exc_tb))
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = log_uncaught
    ArtilleryCalculator().run()


if __name__ == "__main__":
    main()
