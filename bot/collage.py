"""Bir nechta ehson rasmini bitta suratga birlashtirish.

Telegram albomga (sendMediaGroup) inline tugma biriktirishga ruxsat
bermaydi, tugmani alohida xabarga qo'ysak esa uning kengligi qurilma
ekrani va shrift o'lchamiga bog'liq bo'lib qoladi. Rasmlar bitta
suratga birlashtirilsa, tugma sendPhoto bilan yuboriladi va Telegram
uni har doim surat kengligida chizadi.

Joylashuv Telegram albomining o'zini takrorlaydi: ikkita rasm yonma-yon,
uchtasi esa chapda katta, o'ngda ikkita kichik.
"""

import io

from PIL import Image, ImageOps

WIDTH = 1280
GAP = 8
BACKGROUND = (255, 255, 255)
JPEG_QUALITY = 86


def _cell(data: bytes, size: tuple[int, int]) -> Image.Image:
    """Rasmni katakcha nisbatiga markazdan qirqib moslashtiradi."""
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)
    if im.mode != "RGB":
        im = im.convert("RGB")
    return ImageOps.fit(im, size, method=Image.LANCZOS, centering=(0.5, 0.5))


def _layout(count: int) -> tuple[int, list[tuple[int, int, int, int]]]:
    """(balandlik, [(x, y, eni, balandlik), ...]) qaytaradi."""
    if count == 2:
        height = int(WIDTH * 2 / 3)
        half = (WIDTH - GAP) // 2
        return height, [(0, 0, half, height), (half + GAP, 0, WIDTH - half - GAP, height)]
    # uchta rasm: chapda katta, o'ngda ustma-ust ikkita
    height = int(WIDTH * 3 / 4)
    left = int(WIDTH * 0.66)
    right = WIDTH - left - GAP
    top = (height - GAP) // 2
    return height, [
        (0, 0, left, height),
        (left + GAP, 0, right, top),
        (left + GAP, top + GAP, right, height - top - GAP),
    ]


def build_collage(photos: list[bytes]) -> bytes:
    """Ikki yoki uchta rasmdan bitta JPEG yasaydi."""
    if len(photos) < 2:
        raise ValueError("kollaj uchun kamida ikkita rasm kerak")
    photos = photos[:3]
    height, boxes = _layout(len(photos))
    canvas = Image.new("RGB", (WIDTH, height), BACKGROUND)
    for data, (x, y, w, h) in zip(photos, boxes):
        canvas.paste(_cell(data, (w, h)), (x, y))
    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return buf.getvalue()
