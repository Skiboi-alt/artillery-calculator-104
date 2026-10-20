"""Тема и компоненты интерфейса на tkinter.Canvas (скругления, анимации, фокус с клавиатуры)"""

import ctypes
import math
import time
import tkinter as tk
import tkinter.font as tkfont


# ----------------------------------------------------------------------
# Windows: чёткий текст и тёмный заголовок окна
# ----------------------------------------------------------------------

def enable_dpi_awareness():
    """Чёткий текст на мониторах с масштабированием (Windows)"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def apply_dark_titlebar(window, caption_color=None):
    """Тёмная строка заголовка окна в Windows 10/11"""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        dwm = ctypes.windll.dwmapi
        value = ctypes.c_int(1)
        # 20 — DWMWA_USE_IMMERSIVE_DARK_MODE (19 в ранних сборках Windows 10)
        for attribute in (20, 19):
            if dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
        if caption_color:
            # 35 — DWMWA_CAPTION_COLOR (Windows 11), формат COLORREF 0x00BBGGRR
            r, g, b = (int(caption_color[i:i + 2], 16) for i in (1, 3, 5))
            color = ctypes.c_int(r | (g << 8) | (b << 16))
            dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(color), ctypes.sizeof(color))
    except Exception:
        pass


# ----------------------------------------------------------------------
# Палитра и рисование
# ----------------------------------------------------------------------

# Цветовая палитра в стиле 104-го батальона «Волчья стая» (Star Wars: The Clone Wars):
# нейтральные графитовые и серые тона полос на броне, белая броня клонов как акцент
# и красный кибернетический глаз командира Вульфа — только для ошибок
COLORS = {
    "bg": "#0e0e0f",              # Фон окна — чёрный визор
    "surface": "#171718",         # Карточки
    "surface_2": "#1f1f21",       # Поля ввода, переключатели
    "surface_3": "#2c2c2e",       # Выбранный сегмент, hover
    "surface_4": "#38383b",       # Нажатие
    "border": "#29292b",
    "border_strong": "#3d3d40",
    "text": "#f2f2f0",            # Белая броня клонов
    "text_muted": "#9a9a9c",      # Серые полосы
    "text_faint": "#5e5e61",
    "text_ghost": "#3f3f42",      # Недоступные варианты
    "watermark": "#1e1e20",
    "accent": "#e6e6e3",          # Белая броня — главный акцент
    "accent_hover": "#ffffff",
    "accent_press": "#c8c8c5",
    "accent_text": "#111112",     # Тёмный текст на белом
    "accent_soft": "#3a3a3d",     # Выделение текста
    "success": "#d4d4d1",
    "success_soft": "#2e2e30",
    "error": "#e5383b",           # Красный глаз Вульфа
    "error_soft": "#3a161a",
    "transparent": "#010203",     # Ключевой цвет прозрачности для уведомлений
}


def blend_color(color_from, color_to, t):
    """Смешать два цвета #rrggbb: t=0 — первый, t=1 — второй"""
    t = max(0.0, min(1.0, t))
    a = [int(color_from[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(color_to[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


class Tween:
    """Плавное изменение числа во времени (ease-in-out) с вызовом setter на каждом кадре"""

    FRAME_MS = 10

    def __init__(self, widget, setter, duration_ms=180, easing="in_out"):
        self.widget = widget
        self.setter = setter
        self.duration_ms = duration_ms
        self.easing = easing
        self._job = None

    def _ease(self, progress):
        if self.easing == "out":
            return 1 - (1 - progress) ** 3
        # Мягкий разгон и мягкое торможение (ease-in-out cubic)
        if progress < 0.5:
            return 4 * progress ** 3
        return 1 - (-2 * progress + 2) ** 3 / 2

    def start(self, value_from, value_to):
        self.stop()
        started = time.perf_counter()

        def step():
            self._job = None
            try:
                progress = min(1.0, (time.perf_counter() - started) * 1000 / self.duration_ms)
                self.setter(value_from + (value_to - value_from) * self._ease(progress))
                if progress < 1.0:
                    self._job = self.widget.after(self.FRAME_MS, step)
            except tk.TclError:
                pass  # Виджет уничтожен посреди анимации

        step()

    def stop(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None


def round_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    """Скруглённый прямоугольник на Canvas (сглаженный полигон)"""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


# Эмблема 104-го батальона «Волчья стая»: угловатая голова волка анфас.
# Координаты левой половины в сетке 100×100, правая получается зеркально.
WOLF_HALF_OUTLINE = [
    (50, 30), (39, 25), (21, 4), (17, 33), (6, 42), (15, 50),
    (4, 61), (23, 66), (35, 81), (50, 96),
]
WOLF_EAR_INNER = [(23, 12), (35, 27), (25, 33)]
WOLF_EYE = [(27, 44), (44, 51), (32, 54)]
WOLF_MUZZLE = [(46, 57), (54, 57), (52, 72), (48, 72)]
WOLF_NOSE = [(43, 77), (57, 77), (50, 86)]


def wolf_shapes():
    """Полигоны эмблемы в сетке 100×100: (контур, [вырезы], левый глаз, правый глаз)"""
    def mirror(points):
        return [(100 - x, y) for x, y in points]

    outline = WOLF_HALF_OUTLINE + mirror(WOLF_HALF_OUTLINE[::-1])
    cutouts = []
    for shape in (WOLF_EAR_INNER, WOLF_MUZZLE, WOLF_NOSE):
        cutouts += [shape, mirror(shape)]
    return outline, cutouts, WOLF_EYE, mirror(WOLF_EYE)


def draw_wolf(canvas, x, y, size, fill, cutout, eye_left=None, eye_right=None):
    """Нарисовать голову волка в квадрате (x, y, size)"""
    def place(points):
        return [coord for px_, py_ in points for coord in (x + px_ * size / 100, y + py_ * size / 100)]

    outline, cutouts, left_eye, right_eye = wolf_shapes()
    canvas.create_polygon(place(outline), fill=fill, outline=fill)
    for shape in cutouts:
        canvas.create_polygon(place(shape), fill=cutout, outline=cutout)
    canvas.create_polygon(place(left_eye), fill=eye_left or cutout, outline=eye_left or cutout)
    canvas.create_polygon(place(right_eye), fill=eye_right or cutout, outline=eye_right or cutout)


def draw_armor_stripes(canvas, x, y, height, colors, width=None, gap=None):
    """Наклонные полосы, как маркировка на броне клонов"""
    width = width or height * 1.6
    gap = gap or height * 0.5
    for i, color in enumerate(colors):
        left = x + i * (width + gap)
        canvas.create_polygon(left + height, y, left + height + width, y,
                              left + width, y + height, left, y + height,
                              fill=color, outline=color)


class Theme:
    """Шрифты и масштаб интерфейса (зависит от DPI экрана)"""

    def __init__(self, root):
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96)
        families = set(tkfont.families(root))

        def pick(*names):
            for name in names:
                if name in families:
                    return name
            return "TkDefaultFont"

        ui = pick("Segoe UI", "Helvetica", "Arial")
        semibold = pick("Segoe UI Semibold")
        numbers = pick("Bahnschrift SemiBold", "Bahnschrift", "Segoe UI Semibold", "Segoe UI")

        def strong(size):
            return (semibold, size) if semibold != "TkDefaultFont" else (ui, size, "bold")

        self.title = strong(15)
        self.subtitle = (ui, 8)
        self.caption = strong(8)
        self.body = (ui, 10)
        self.body_strong = strong(10)
        self.small = (ui, 9)
        self.input = (ui, 12)
        self.button = strong(10)
        self.button_large = strong(11)
        self.result_big = (numbers, 46)
        self.result_unit = (numbers, 16)
        self.stat = (numbers, 18)
        self.history_value = (numbers, 12)

    def px(self, value):
        return int(round(value * self.scale))


# ----------------------------------------------------------------------
# Компоненты
# ----------------------------------------------------------------------

class FocusableCanvas(tk.Canvas):
    """Canvas, который можно выбрать клавишей Tab; рисует рамку фокуса"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, takefocus=1, **kwargs)
        self.has_focus = False
        self._mouse_focus = False
        self.bind("<FocusIn>", lambda e: self._set_focus(True), add="+")
        self.bind("<FocusOut>", lambda e: self._set_focus(False), add="+")
        # Клик тоже даёт фокус. Отдельный bindtag идёт раньше привязок самого виджета,
        # поэтому подклассы могут свободно переопределять <Button-1>
        tag = f"FocusOnClick{id(self)}"
        self.bind_class(tag, "<ButtonPress-1>", self._focus_by_mouse)
        self.bindtags((tag,) + self.bindtags())

    def _focus_by_mouse(self, event):
        if self.focus_get() is self:
            self.has_focus = False   # Уже в фокусе — после клика рамку прячем
        else:
            self._mouse_focus = True
            self.focus_set()

    def _set_focus(self, focused):
        # Рамку показываем только при навигации с клавиатуры, а не после клика мышью
        self.has_focus = focused and not self._mouse_focus
        self._mouse_focus = False
        self._redraw()

    def _redraw(self):
        raise NotImplementedError


class RoundedPanel(tk.Canvas):
    """Карточка со скруглёнными углами; содержимое кладётся в .inner"""

    def __init__(self, parent, theme, bg, parent_bg, radius=14, padding=20,
                 border=None, fill_y=False):
        # width=1: ширину задаёт содержимое/раскладка, а не дефолт Canvas (~380px)
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0, width=1)
        self.theme = theme
        self.fill_color = bg
        self.border = border
        self.base_border = border
        self.radius = theme.px(radius)
        self.padding = theme.px(padding)
        self.fill_y = fill_y
        self.inner = tk.Frame(self, bg=bg)
        self._window = self.create_window(self.padding, self.padding, window=self.inner, anchor="nw")
        self._flash = Tween(self, self._set_flash, duration_ms=700, easing="out")
        self._flash_color = None
        self.bind("<Configure>", self._redraw)
        self.inner.bind("<Configure>", self._fit_height)

    def _fit_height(self, event=None):
        self.config(width=self.inner.winfo_reqwidth() + 2 * self.padding,
                    height=self.inner.winfo_reqheight() + 2 * self.padding)

    def flash(self, color):
        """Коротко подсветить рамку карточки и плавно вернуть обычный цвет"""
        self._flash_color = color
        self._flash.start(0.0, 1.0)

    def _set_flash(self, t):
        self.border = blend_color(self._flash_color, self.base_border or self.fill_color, t)
        self._redraw()

    def _redraw(self, event=None):
        w, h = self.winfo_width(), self.winfo_height()
        self.delete("bg")
        round_rect(self, 1, 1, w - 1, h - 1, self.radius, fill=self.fill_color,
                   outline=self.border or self.fill_color, tags="bg")
        self.tag_lower("bg")
        self.itemconfig(self._window, width=max(1, w - 2 * self.padding))
        if self.fill_y:
            self.itemconfig(self._window, height=max(1, h - 2 * self.padding))


class RoundedButton(FocusableCanvas):
    """Кнопка со скруглёнными углами, плавной сменой цвета и управлением с клавиатуры"""

    VARIANTS = {
        "primary": ("accent", "accent_hover", "accent_press", "accent_text", None),
        "secondary": ("surface_2", "surface_3", "surface_4", "text", "border_strong"),
        "danger": ("surface_2", "error_soft", "error_soft", "error", "border_strong"),
    }

    def __init__(self, parent, theme, text, command, parent_bg, variant="primary",
                 height=44, width=None, font=None):
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0,
                         height=theme.px(height), width=theme.px(width or 80), cursor="hand2")
        self.theme = theme
        self.text = text
        self.command = command
        self.font = font or theme.button
        bg, hover, press, fg, border = self.VARIANTS[variant]
        self.colors = {
            "normal": COLORS[bg], "hover": COLORS[hover], "press": COLORS[press],
            "fg": COLORS[fg], "border": COLORS[border] if border else None,
        }
        self.fill = self.colors["normal"]
        self._fade_from = self.fill
        self._fade_to = self.fill
        self._fade = Tween(self, self._set_fade, duration_ms=140, easing="out")
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Enter>", lambda e: self._go("hover"))
        self.bind("<Leave>", lambda e: self._go("normal"))
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<KeyPress-space>", lambda e: self._invoke())
        self.bind("<Return>", lambda e: self._invoke())
        self.bind("<KP_Enter>", lambda e: self._invoke())

    def _go(self, state, animate=True):
        target = self.colors[state]
        if animate:
            self._fade_from, self._fade_to = self.fill, target
            self._fade.start(0.0, 1.0)
        else:
            self._fade.stop()
            self.fill = target
            self._redraw()

    def _set_fade(self, t):
        self.fill = blend_color(self._fade_from, self._fade_to, t)
        self._redraw()

    def _on_press(self, event):
        self._go("press", animate=False)

    def _on_release(self, event):
        inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        self._go("hover" if inside else "normal")
        if inside and self.command:
            self.command()

    def _invoke(self):
        if self.command:
            self.command()
        return "break"  # Не передавать Enter главному окну (иначе ещё и расчёт)

    def set_text(self, text):
        self.text = text
        self._redraw()

    def _redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            return
        self.delete("all")
        border = self.colors["border"] if self.colors["border"] else self.fill
        if self.has_focus:
            border = COLORS["accent"] if self.colors["border"] else COLORS["text_muted"]
        round_rect(self, 1, 1, w - 1, h - 1, self.theme.px(10), fill=self.fill, outline=border,
                   width=2 if self.has_focus else 1)
        self.create_text(w / 2, h / 2, text=self.text, font=self.font, fill=self.colors["fg"])


class SegmentedControl(FocusableCanvas):
    """Переключатель из нескольких сегментов (замена радиокнопкам и комбобоксу).

    Стрелки ←/→ переключают сегменты, когда переключатель выбран клавишей Tab.
    """

    def __init__(self, parent, theme, variable, options, parent_bg, command=None, height=40):
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0,
                         height=theme.px(height), width=theme.px(200), cursor="hand2")
        self.theme = theme
        self.variable = variable
        self.options = options
        self.command = command
        self.hover_index = None
        self.suggested = None   # Индексы рекомендуемых сегментов (None — без подсказки)
        # Положение подсветки в «индексах» сегментов (дробное во время анимации)
        self.position = self._current_index()
        self.tween = Tween(self, self._set_position, duration_ms=250)
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", self._on_click)
        self.bind("<Left>", lambda e: self._step(-1))
        self.bind("<Right>", lambda e: self._step(1))
        variable.trace_add("write", lambda *args: self._on_variable_change())

    def _current_index(self):
        current = str(self.variable.get())
        for i, (value, _) in enumerate(self.options):
            if str(value) == current:
                return float(i)
        return None

    def _set_position(self, position):
        self.position = position
        self._redraw()

    def _on_variable_change(self):
        target = self._current_index()
        if target is None or self.position is None:
            self.tween.stop()
            self._set_position(target)
        else:
            self.tween.start(self.position, target)

    def set_options(self, options):
        # Набор сегментов сменился (другое орудие) — подсветку ставим сразу, без анимации
        self.options = options
        self.suggested = None
        self.tween.stop()
        self._set_position(self._current_index())

    def set_suggested(self, values):
        """Подсветить подходящие варианты, остальные приглушить (None — убрать подсказку)"""
        if values is None:
            self.suggested = None
        else:
            wanted = {str(v) for v in values}
            self.suggested = {i for i, (value, _) in enumerate(self.options) if str(value) in wanted}
        self._redraw()

    def _select(self, index):
        value = self.options[index][0]
        if str(self.variable.get()) != str(value):
            self.variable.set(value)
            if self.command:
                self.command()

    def _step(self, delta):
        current = self._current_index()
        if current is not None and self.options:
            self._select(max(0, min(len(self.options) - 1, int(current) + delta)))
        return "break"

    def _index_at(self, x):
        pad = self.theme.px(4)
        width = (self.winfo_width() - 2 * pad) / max(1, len(self.options))
        return max(0, min(len(self.options) - 1, int((x - pad) // width)))

    def _set_hover(self, index):
        if index != self.hover_index:
            self.hover_index = index
            self._redraw()

    def _on_motion(self, event):
        self._set_hover(self._index_at(event.x))

    def _on_click(self, event):
        if self.options:
            self._select(self._index_at(event.x))

    def _redraw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or not self.options:
            return
        self.delete("all")
        px = self.theme.px
        pad = px(4)
        round_rect(self, 1, 1, w - 1, h - 1, px(10), fill=COLORS["surface_2"],
                   outline=COLORS["accent"] if self.has_focus else COLORS["border"],
                   width=2 if self.has_focus else 1)
        seg_w = (w - 2 * pad) / len(self.options)
        if self.position is not None:
            x1 = pad + self.position * seg_w
            round_rect(self, x1, pad, x1 + seg_w, h - pad, px(7),
                       fill=COLORS["surface_3"], outline=COLORS["border_strong"])
        for i, (value, label) in enumerate(self.options):
            # Насколько подсветка «накрывает» сегмент: 1 — полностью, 0 — далеко
            closeness = 0.0 if self.position is None else max(0.0, 1 - abs(i - self.position))
            if self.suggested is not None and i not in self.suggested:
                base = COLORS["text_ghost"]  # Заряд не достаёт до цели
            elif i == self.hover_index:
                base = COLORS["text"]
            else:
                base = COLORS["text_muted"]
            color = blend_color(base, COLORS["text"], closeness)
            font = self.theme.body_strong if closeness > 0.5 else self.theme.body
            self.create_text(pad + i * seg_w + seg_w / 2, h / 2, text=label, font=font, fill=color)


class InputField(tk.Frame):
    """Подпись + поле ввода со скруглённой рамкой, подсказкой и единицей измерения"""

    def __init__(self, parent, theme, label, parent_bg, suffix="", numeric=True, placeholder="", height=44):
        super().__init__(parent, bg=parent_bg)
        self.theme = theme
        self.suffix = suffix
        self.numeric = numeric
        self.placeholder = placeholder
        self.focused = False
        self.invalid = False
        self.error_mark = False    # Подсветка после неудачного расчёта (до следующего ввода)
        self._placeholder_shown = False

        # Без подписи (label="") — компактное поле, например «шаг корректировки»
        self.label = tk.Label(self, text=label.upper(), font=theme.caption, fg=COLORS["text_muted"],
                              bg=parent_bg, anchor="w")
        if label:
            self.label.pack(fill=tk.X, pady=(0, theme.px(6)))

        self.box = tk.Canvas(self, bg=parent_bg, highlightthickness=0, bd=0,
                             height=theme.px(height), width=theme.px(60 if not label else 120))
        self.box.pack(fill=tk.X)
        self.entry = tk.Entry(
            self.box, font=theme.input, bg=COLORS["surface_2"], fg=COLORS["text"],
            insertbackground=COLORS["accent"], disabledbackground=COLORS["surface_2"],
            selectbackground=COLORS["accent_soft"], selectforeground=COLORS["text"],
            relief=tk.FLAT, bd=0, highlightthickness=0,
        )
        self._window = self.box.create_window(theme.px(14), theme.px(22), window=self.entry, anchor="w")

        self.box.bind("<Configure>", lambda e: self._redraw())
        self.box.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry.bind("<FocusIn>", lambda e: self._set_focus(True), add="+")
        self.entry.bind("<FocusOut>", lambda e: self._set_focus(False), add="+")
        self.entry.bind("<KeyRelease>", self._on_key, add="+")
        self._show_placeholder()

    # --- значение ---

    def get(self):
        return "" if self._placeholder_shown else self.entry.get()

    def set(self, value):
        self._hide_placeholder()
        self.entry.delete(0, tk.END)
        self.entry.insert(0, value)
        self.error_mark = False
        if not self.focused:
            self._show_placeholder()
        self._validate()

    # --- подсказка в пустом поле ---

    def _show_placeholder(self):
        if self.placeholder and not self.entry.get():
            self.entry.insert(0, self.placeholder)
            self.entry.config(fg=COLORS["text_faint"])
            self._placeholder_shown = True

    def _hide_placeholder(self):
        if self._placeholder_shown:
            self.entry.delete(0, tk.END)
            self.entry.config(fg=COLORS["text"])
            self._placeholder_shown = False

    # --- состояние ---

    def mark_error(self):
        """Подсветить поле красным и поставить в него курсор"""
        self.error_mark = True
        self.entry.focus_set()
        self._redraw()

    def _on_key(self, event):
        self.error_mark = False
        self._validate()

    def _set_focus(self, focused):
        self.focused = focused
        if focused:
            self._hide_placeholder()
        else:
            self._show_placeholder()
        self._validate()

    def _validate(self):
        invalid = False
        value = self.get().strip()
        if self.numeric and value:
            try:
                invalid = not math.isfinite(float(value.replace(",", ".")))
            except ValueError:
                invalid = True
        self.invalid = invalid
        self._redraw()

    def _redraw(self):
        px = self.theme.px
        w, h = self.box.winfo_width(), self.box.winfo_height()
        if w <= 1:
            return
        self.box.delete("frame")
        highlighted = self.invalid or self.error_mark
        if highlighted:
            outline = COLORS["error"]
        elif self.focused:
            outline = COLORS["accent"]
        else:
            outline = COLORS["border"]
        round_rect(self.box, 1, 1, w - 1, h - 1, px(10), fill=COLORS["surface_2"],
                   outline=outline, width=2 if (self.focused or highlighted) else 1, tags="frame")
        if self.suffix:
            self.box.create_text(w - px(14), h / 2, text=self.suffix, anchor="e", font=self.theme.body,
                                 fill=COLORS["text_faint"], tags="frame")
        self.box.tag_lower("frame")
        suffix_space = px(36) if self.suffix else px(14)
        self.box.coords(self._window, px(14), h / 2)
        self.box.itemconfig(self._window, width=max(1, w - px(14) - suffix_space))


class HistoryList(tk.Canvas):
    """Последние расчёты: клик по строке — вернуть её параметры. Пустой список — водяной знак стаи."""

    def __init__(self, parent, theme, parent_bg, on_select, on_clear):
        super().__init__(parent, bg=parent_bg, highlightthickness=0, bd=0, width=1, height=1)
        self.theme = theme
        self.parent_bg = parent_bg
        self.on_select = on_select
        self.on_clear = on_clear
        self.items = []
        self.hover = None
        self._row_boxes = []      # (y1, y2, item) видимых строк
        self._clear_box = None
        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<Button-1>", self._on_click)

    def set_items(self, items):
        self.items = list(items)
        self._redraw()

    def _hit(self, y):
        for y1, y2, item in self._row_boxes:
            if y1 <= y <= y2:
                return item
        return None

    def _set_hover(self, item):
        if item is not self.hover:
            self.hover = item
            self.config(cursor="hand2" if item is not None else "")
            self._redraw()

    def _on_motion(self, event):
        if self._clear_box and self._in_box(self._clear_box, event):
            self._set_hover(None)
            self.config(cursor="hand2")  # После _set_hover, который сбрасывает курсор
            return
        self._set_hover(self._hit(event.y))

    @staticmethod
    def _in_box(box, event):
        x1, y1, x2, y2 = box
        return x1 <= event.x <= x2 and y1 <= event.y <= y2

    def _on_click(self, event):
        if self._clear_box and self._in_box(self._clear_box, event):
            self.on_clear()
            return
        item = self._hit(event.y)
        if item is not None:
            self.on_select(item)

    def _redraw(self):
        self.delete("all")
        px = self.theme.px
        w, h = self.winfo_width(), self.winfo_height()
        self._row_boxes = []
        self._clear_box = None
        if w <= 1 or h <= 1:
            return
        if not self.items:
            self._draw_watermark(w, h)
            return

        top = px(18)
        self.create_text(0, px(8), text="ИСТОРИЯ", anchor="w", font=self.theme.caption, fill=COLORS["text_muted"])
        clear_id = self.create_text(w, px(8), text="очистить", anchor="e", font=self.theme.small,
                                    fill=COLORS["text_faint"])
        x1, y1, x2, y2 = self.bbox(clear_id)
        self._clear_box = (x1 - px(4), y1 - px(4), x2 + px(4), y2 + px(4))

        row_h = px(30)
        visible = max(0, (h - top) // row_h)
        for i, item in enumerate(self.items[:visible]):
            y1 = top + i * row_h
            y2 = y1 + row_h - px(4)
            if item is self.hover:
                round_rect(self, 0, y1, w, y2, px(8), fill=COLORS["surface_2"], outline=COLORS["border"])
            cy = (y1 + y2) / 2
            value_id = self.create_text(px(10), cy, text=f"{item['elevation']:.1f}", anchor="w",
                                        font=self.theme.history_value, fill=COLORS["text"])
            vx2 = self.bbox(value_id)[2]
            self.create_text(vx2 + px(4), cy + px(1), text="MIL", anchor="w", font=self.theme.small,
                             fill=COLORS["text_faint"])
            self.create_text(w - px(10), cy, text=item.get("time", ""), anchor="e", font=self.theme.small,
                             fill=COLORS["text_faint"])
            self.create_text(vx2 + px(40), cy, text=item.get("summary", ""), anchor="w",
                             font=self.theme.small, fill=COLORS["text_muted"])
            self._row_boxes.append((y1, y2, item))

    def _draw_watermark(self, w, h):
        px = self.theme.px
        size = min(w, h - px(24)) * 0.8
        if size < px(40):
            return
        x = (w - size) / 2
        y = (h - size - px(20)) / 2
        draw_wolf(self, x, y, size, COLORS["watermark"], self.parent_bg)
        self.create_text(w / 2, y + size + px(14), text="W O L F P A C K",
                         font=self.theme.caption, fill=COLORS["border"])
