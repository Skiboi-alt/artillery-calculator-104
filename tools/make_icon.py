"""Сгенерировать icon.ico с эмблемой «Волчьей стаи» (та же, что в шапке программы).

Нужен Pillow (только для этого скрипта, программе он не нужен):
    pip install pillow
    python tools/make_icon.py
"""

import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ui_widgets import COLORS, wolf_shapes  # noqa: E402

SIZES = [16, 24, 32, 48, 64, 128, 256]
SUPERSAMPLE = 4  # Рисуем крупно и уменьшаем — сглаженные края


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

    outline, cutouts, left_eye, right_eye = wolf_shapes()
    draw.polygon(place(outline), fill=COLORS["accent"])
    for shape in cutouts:
        draw.polygon(place(shape), fill=COLORS["surface_2"])
    draw.polygon(place(left_eye), fill=COLORS["surface_2"])
    draw.polygon(place(right_eye), fill=COLORS["error"])  # Красный глаз Вульфа
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

    outline, cutouts, left_eye, right_eye = wolf_shapes()
    draw.polygon(place(outline), fill=COLORS["accent"])
    for shape in cutouts:
        draw.polygon(place(shape), fill=COLORS["surface_2"])
    draw.polygon(place(left_eye), fill=COLORS["surface_2"])
    draw.polygon(place(right_eye), fill=COLORS["error"])
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
