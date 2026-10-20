"""Сгенерировать icon.ico с эмблемой «Волчьей стаи» (тема по умолчанию, как в шапке программы).

Нужен Pillow (только для этого скрипта, программе он не нужен):
    pip install pillow
    python tools/make_icon.py
"""

import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import themes  # noqa: E402

UNIT = themes.get_theme(themes.DEFAULT_THEME)
COLORS = UNIT["colors"]

SIZES = [16, 24, 32, 48, 64, 128, 256]
SUPERSAMPLE = 4  # Рисуем крупно и уменьшаем — сглаженные края


def draw_emblem(draw, place, plate):
    """Слои эмблемы темы; place переводит точки сетки 100×100 в пиксели"""
    colors = themes.emblem_colors(COLORS, plate)
    for role, points in UNIT["emblem"]:
        draw.polygon(place(points), fill=colors[role])


def render(size):
    big = size * SUPERSAMPLE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    radius = big * 0.22
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=radius, fill=COLORS["surface_2"],
                           outline=COLORS["border_strong"], width=max(1, big // 64))

    margin = big * 0.12
    scale = (big - 2 * margin) / 100

    def place(points):
        return [(margin + x * scale, margin + y * scale) for x, y in points]

    draw_emblem(draw, place, COLORS["surface_2"])
    return image.resize((size, size), Image.LANCZOS)


def render_full_bleed(size, wolf_scale):
    """Квадрат без прозрачности (для иконок телефона: maskable и apple-touch-icon).

    wolf_scale — доля стороны под волка; у maskable лишнее обрезает форма иконки системы.
    """
    big = size * SUPERSAMPLE
    image = Image.new("RGB", (big, big), COLORS["surface_2"])
    draw = ImageDraw.Draw(image)
    wolf = big * wolf_scale
    offset = (big - wolf) / 2
    scale = wolf / 100

    def place(points):
        return [(offset + x * scale, offset + y * scale) for x, y in points]

    draw_emblem(draw, place, COLORS["surface_2"])
    return image.resize((size, size), Image.LANCZOS)


def main():
    images = [render(s) for s in SIZES]
    target = os.path.join(ROOT, "icon.ico")
    images[-1].save(target, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    images[-1].save(os.path.join(ROOT, "tools", "icon_preview.png"))
    print("Готово:", target)

    # Иконки мобильной версии
    mobile = os.path.join(ROOT, "mobile", "icons")
    os.makedirs(mobile, exist_ok=True)
    render(192).save(os.path.join(mobile, "icon-192.png"))
    render(512).save(os.path.join(mobile, "icon-512.png"))
    render_full_bleed(512, 0.58).save(os.path.join(mobile, "maskable-512.png"))      # Безопасная зона ~80%
    render_full_bleed(180, 0.74).save(os.path.join(mobile, "apple-touch-icon.png"))  # iOS скругляет сам
    print("Готово:", mobile)


if __name__ == "__main__":
    main()
