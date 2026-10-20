"""Темы подразделений: палитра, названия и эмблема.

Все палитры содержат одни и те же ключи, что и ui_widgets.COLORS. Эмблема — набор слоёв-полигонов
в сетке 100×100; цвет слоя задаётся ролью:
    fill — основная форма (голова волка, клинок и глаз, маска)
    cut  — вырезы и зазоры — цветом подложки
    mark — цвет подразделения (радужка ока, бордовая каска)
    eye  — особый цвет (красный глаз Вульфа)
    dark — почти чёрные детали (зрачок, тень под козырьком)
    fold — складки ткани
Тот же модуль выгружается в мобильную версию (tools/export_mobile.py).
"""

import math

DEFAULT_THEME = "wolfpack"


def _mirror(points):
    return [(100 - x, y) for x, y in points]


def _symmetric(half):
    """Замкнутый контур из левой половины (сверху вниз по оси x=50) и её зеркала"""
    return half + _mirror(half[::-1])


def _pair(shape):
    """Деталь и её зеркальная копия"""
    return [shape, _mirror(shape)]


def _circle(cx, cy, r, n=32):
    return [(round(cx + r * math.cos(2 * math.pi * i / n), 2), round(cy + r * math.sin(2 * math.pi * i / n), 2))
            for i in range(n)]


def _bezier(p0, p1, p2, p3, n=16):
    """Кубическая кривая Безье, без начальной точки (для склейки с предыдущим отрезком)"""
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        out.append((round(u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0], 2),
                    round(u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1], 2)))
    return out


def _scaled(points, kx, ky, cx=50, cy=50):
    return [(round(cx + (x - cx) * kx, 2), round(cy + (y - cy) * ky, 2)) for x, y in points]


# ----------------------------------------------------------------------
# Эмблемы
# ----------------------------------------------------------------------

# 104-й «Волчья стая»: угловатая голова волка анфас
WOLF_HALF_OUTLINE = [
    (50, 30), (39, 25), (21, 4), (17, 33), (6, 42), (15, 50),
    (4, 61), (23, 66), (35, 81), (50, 96),
]
WOLF_EAR_INNER = [(23, 12), (35, 27), (25, 33)]
WOLF_EYE = [(27, 44), (44, 51), (32, 54)]
WOLF_MUZZLE = [(46, 57), (54, 57), (52, 72), (48, 72)]
WOLF_NOSE = [(43, 77), (57, 77), (50, 86)]


def _wolf_layers():
    layers = [("fill", _symmetric(WOLF_HALF_OUTLINE))]
    for shape in (WOLF_EAR_INNER, WOLF_MUZZLE, WOLF_NOSE):
        layers += [("cut", s) for s in _pair(shape)]
    layers.append(("cut", WOLF_EYE))
    layers.append(("eye", _mirror(WOLF_EYE)))   # Один глаз красный — как у командира Вульфа
    return layers


# 5-й ОКО | Shadow: око с красной радужкой перед кинжалом — знак контрразведки
def _eye_dagger_layers():
    layers = [("fill", _circle(50, 7, 4, 24))]                                         # Навершие
    layers.append(("fill", [(46.5, 9), (53.5, 9), (53.5, 25), (46.5, 25)]))           # Рукоять
    layers.append(("fill", _symmetric([(50, 25), (30, 25), (27, 28.5), (30, 32), (50, 32)])))  # Гарда
    layers.append(("fill", _symmetric([(50, 32), (43.5, 32), (43.5, 76), (50, 96)])))  # Клинок
    layers.append(("cut", _symmetric([(50, 36), (49, 36), (49, 75), (50, 81)])))      # Дол
    eye = [(12, 54)] + _bezier((12, 54), (29, 35), (71, 35), (88, 54))         + _bezier((88, 54), (71, 73), (29, 73), (12, 54))[:-1]
    layers.append(("cut", _scaled(eye, 1.08, 1.25, 50, 54)))                          # Зазор вокруг глаза
    layers.append(("fill", eye))
    layers.append(("dark", _scaled(eye, 0.86, 0.78, 50, 54)))
    layers.append(("mark", _circle(50, 54, 10, 40)))                                   # Радужка
    layers.append(("dark", _circle(50, 54, 4, 24)))                                   # Зрачок
    layers.append(("fill", _circle(53, 51, 1.6, 12)))                                 # Блик
    return layers


# 21-й ОШБ: бордовая каска с боковыми щитками, тень под козырьком и белая тканевая маска
# (обведено по скриншотам из игры)
MARINE_HELMET = [
    ("mark", [(50.0, 4.0), (40.6, 4.7), (31.3, 7.6), (23.4, 13.0), (18.3, 20.9), (15.5, 31.7), (14.0, 43.6), (11.1, 56.2), (8.6, 74.2), (8.3, 85.0), (11.1, 88.6), (15.5, 85.7), (18.3, 67.0), (21.2, 49.7), (50.0, 49.7), (50.0, 49.7), (78.8, 49.7), (81.7, 67.0), (84.5, 85.7), (88.9, 88.6), (91.7, 85.0), (91.4, 74.2), (88.9, 56.2), (86.0, 43.6), (84.5, 31.7), (81.7, 20.9), (76.6, 13.0), (68.7, 7.6), (59.4, 4.7), (50.0, 4.0)]),
    ("dark", [(50.0, 45.4), (21.9, 45.4), (21.2, 56.2), (50.0, 57.6), (50.0, 57.6), (78.8, 56.2), (78.1, 45.4), (50.0, 45.4)]),
    ("fill", [(50.0, 55.5), (39.9, 51.9), (31.3, 49.0), (24.4, 51.1), (21.9, 62.7), (11.9, 84.2), (6.8, 96.0), (93.2, 96.0), (88.1, 84.2), (78.1, 62.7), (75.6, 51.1), (68.7, 49.0), (60.1, 51.9), (50.0, 55.5)]),
    ("fold", [(25.5, 64.1), (39.9, 77.8), (38.5, 79.9), (23.7, 67.0)]),
    ("fold", [(75.9, 64.1), (61.5, 82.1), (63.7, 83.5), (78.1, 67.7)]),
]


# ----------------------------------------------------------------------
# Темы
# ----------------------------------------------------------------------

THEMES = {
    # 104-й батальон «Волчья стая»: графит и белая броня, красный — только глаз Вульфа и ошибки
    "wolfpack": {
        "name": "104-й ДОБ «Волчья стая»",
        "short": "104-й ДОБ",
        "of": "104-го ДОБ",              # «калькулятор 104-го ДОБ»
        "title": "104-Й ДОБ  «ВОЛЧЬЯ СТАЯ»",
        "watermark": "W O L F P A C K",
        "emblem": _wolf_layers(),
        "colors": {
            "bg": "#0e0e0f", "surface": "#171718", "surface_2": "#1f1f21", "surface_3": "#2c2c2e",
            "surface_4": "#38383b", "border": "#29292b", "border_strong": "#3d3d40",
            "text": "#f2f2f0", "text_muted": "#9a9a9c", "text_faint": "#5e5e61", "text_ghost": "#3f3f42",
            "watermark": "#1e1e20",
            "accent": "#e6e6e3", "accent_hover": "#ffffff", "accent_press": "#c8c8c5",
            "accent_text": "#111112", "accent_soft": "#3a3a3d",
            "success": "#d4d4d1", "success_soft": "#2e2e30",
            "error": "#e5383b", "error_soft": "#3a161a",
            "emblem": "#e6e6e3", "mark": "#e6e6e3",
            "transparent": "#010203",
        },
    },
    # 5-й ОКО | Shadow — Бригада контрразведывательных операций: чёрная броня с белыми полосами
    # и красным визором. Ошибки — янтарные, чтобы не путались с красным акцентом
    "bko": {
        "name": "5-й ОКО | Shadow",
        "short": "5-й ОКО",
        "of": "5-го ОКО",
        "title": "5-Й ОКО  |  SHADOW",
        "watermark": "S H A D O W",
        "emblem": _eye_dagger_layers(),
        "colors": {
            "bg": "#0b0b0c", "surface": "#141415", "surface_2": "#1c1c1e", "surface_3": "#29292b",
            "surface_4": "#353537", "border": "#262628", "border_strong": "#3a3a3c",
            "text": "#f0f0f0", "text_muted": "#9c9c9f", "text_faint": "#606063", "text_ghost": "#3f3f42",
            "watermark": "#1e1e20",
            "accent": "#d42a2e", "accent_hover": "#e43d40", "accent_press": "#b32225",
            "accent_text": "#ffffff", "accent_soft": "#4a1719",
            "success": "#dedede", "success_soft": "#2c2c2e",
            "error": "#ff9a3c", "error_soft": "#3d2812",
            "emblem": "#ededed", "mark": "#e0282c",
            "transparent": "#010203",
        },
    },
    # 21-й ОШБ — орбитально-штурмовой батальон: бордовая броня с белыми деталями, как на флагах.
    # Ошибки — янтарные, чтобы не путались с бордовым акцентом
    "marines": {
        "name": "21-й Орбитально-штурмовой батальон",
        "short": "21-й ОШБ",
        "of": "21-го ОШБ",
        "title": "21-Й ОРБИТАЛЬНО-ШТУРМОВОЙ БАТАЛЬОН",
        "watermark": "N O V A   C O R P S",
        "emblem": MARINE_HELMET,
        "colors": {
            "bg": "#0e0c0d", "surface": "#161314", "surface_2": "#1e1a1c", "surface_3": "#2b2528",
            "surface_4": "#373034", "border": "#282325", "border_strong": "#3d3539",
            "text": "#f2eff0", "text_muted": "#a39a9e", "text_faint": "#655d61", "text_ghost": "#433c40",
            "watermark": "#211c1e",
            "accent": "#9e2f52", "accent_hover": "#b23d62", "accent_press": "#842644",
            "accent_text": "#ffffff", "accent_soft": "#451f2d",
            "success": "#e6dde0", "success_soft": "#2d2629",
            "error": "#ff8a3d", "error_soft": "#3d2513",
            "emblem": "#ecebec", "mark": "#8c2747",
            "transparent": "#010203",
        },
    },
}

THEME_ORDER = ["wolfpack", "bko", "marines"]


def get_theme(key):
    """Тема по ключу; неизвестный ключ — тема по умолчанию"""
    return THEMES.get(key, THEMES[DEFAULT_THEME])


def theme_key(key):
    return key if key in THEMES else DEFAULT_THEME


def emblem_colors(colors, plate):
    """Цвета ролей эмблемы на подложке plate"""
    return {"fill": colors["emblem"], "cut": plate, "mark": colors["mark"], "eye": colors["error"],
            "dark": colors["bg"], "fold": colors["text_muted"]}


def watermark_colors(colors, plate):
    """Водяной знак: одна приглушённая форма, детали — цветом фона"""
    return {"fill": colors["watermark"], "cut": plate, "mark": colors["watermark"], "eye": plate,
            "dark": plate, "fold": plate}
