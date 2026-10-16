"""内置背景--4 款纯程序生成的底图(零版权,零素材,可调色).

对应效果预研定案:黄昏晚霞 / 深夜星河 / 海盐渐变 / 暮紫渐变.
(远山晨雾 / 暖阳微光 转备用,以后想要再开.)
"""
from __future__ import annotations

import random

from PIL import Image, ImageDraw, ImageFilter

BACKGROUNDS = {
    "dusk": "黄昏晚霞",
    "night": "深夜星河",
    "sea": "海盐渐变",
    "purple": "暮紫渐变",
}

_ALIASES = {
    "黄昏晚霞": "dusk", "晚霞": "dusk",
    "深夜星河": "night", "星河": "night",
    "海盐渐变": "sea", "海盐": "sea",
    "暮紫渐变": "purple", "暮紫": "purple",
}


def normalize(name: str) -> str:
    """把用户输入(中英文都行)归一成内置背景的代号;不认识的原样返回."""
    v = (name or "").strip()
    return _ALIASES.get(v, v.lower())


def make_background(name: str, size: tuple[int, int] = (1920, 1080)) -> Image.Image:
    """按名字生成一张背景图;不认识的名字一律用'黄昏晚霞'."""
    W, H = size
    name = normalize(name)
    if name == "night":
        return _night(W, H)
    if name == "sea":
        return _sea(W, H)
    if name == "purple":
        return _purple(W, H)
    return _dusk(W, H)


def _vgrad(W: int, H: int, stops) -> Image.Image:
    """竖向多段渐变.stops = [(位置0~1, (r,g,b)), ...] 按位置递增."""
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        c = stops[-1][1]
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                k = (t - p0) / (p1 - p0) if p1 > p0 else 0.0
                c = tuple(int(c0[j] + (c1[j] - c0[j]) * k) for j in range(3))
                break
        d.line([(0, y), (W, y)], fill=c)
    return img


def _deco_y(frac: float, portrait: bool) -> float:
    """竖屏时把山影等底部装饰收进画面下 1/4 左右,别占半屏."""
    if not portrait:
        return frac
    return frac + (1 - frac) * 0.45


def _dusk(W: int, H: int) -> Image.Image:
    """黄昏晚霞"""
    k = W / 1920.0
    img = _vgrad(W, H, [(0, (255, 156, 102)), (0.55, (255, 94, 120)), (1, (66, 46, 96))])
    d = ImageDraw.Draw(img, "RGBA")
    for r, al in [(260, 55), (180, 70), (110, 90), (60, 130)]:
        r = r * k
        d.ellipse([W * 0.62 - r, H * 0.30 - r, W * 0.62 + r, H * 0.30 + r], fill=(255, 228, 160, al))
    portrait = H >= W * 1.5

    def ym(f: float) -> float:
        return H * _deco_y(f, portrait)

    d.polygon([(0, H), (0, ym(0.72)), (W * 0.22, ym(0.52)), (W * 0.40, ym(0.70)),
               (W * 0.55, ym(0.58)), (W * 0.75, ym(0.75)), (W, ym(0.62)), (W, H)], fill=(58, 40, 74))
    d.polygon([(0, H), (0, ym(0.82)), (W * 0.30, ym(0.66)), (W * 0.58, ym(0.84)),
               (W * 0.85, ym(0.70)), (W, ym(0.80)), (W, H)], fill=(40, 28, 56))
    rnd = random.Random(7)
    for _ in range(14):
        cx = rnd.uniform(0, W)
        cy = rnd.uniform(H * 0.05, H * 0.55)
        r = rnd.uniform(6, 22) * k
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 220, 180, 60))
    return img.filter(ImageFilter.GaussianBlur(1.2))


def _night(W: int, H: int) -> Image.Image:
    """深夜星河"""
    k = W / 1920.0
    img = _vgrad(W, H, [(0, (8, 12, 36)), (0.6, (24, 22, 64)), (1, (46, 32, 86))])
    d = ImageDraw.Draw(img, "RGBA")
    mx, my, mr = W * 0.78, H * 0.22, 68 * k
    for r, al in [(mr * 3, 24), (mr * 1.8, 40), (mr, 235)]:
        d.ellipse([mx - r, my - r, mx + r, my + r], fill=(238, 240, 220, al))
    rnd = random.Random(42)
    for _ in range(230):
        x = rnd.uniform(0, W)
        y = rnd.uniform(0, H * 0.75)
        r = rnd.uniform(0.6, 2.2)
        al = rnd.randint(90, 235)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, al))
    portrait = H >= W * 1.5

    def ym(f: float) -> float:
        return H * _deco_y(f, portrait)

    d.polygon([(0, H), (0, ym(0.78)), (W * 0.18, ym(0.60)), (W * 0.38, ym(0.76)),
               (W * 0.60, ym(0.62)), (W * 0.82, ym(0.78)), (W, ym(0.70)), (W, H)], fill=(16, 14, 34))
    d.polygon([(0, H), (0, ym(0.88)), (W * 0.28, ym(0.74)), (W * 0.55, ym(0.88)),
               (W * 0.78, ym(0.76)), (W, ym(0.86)), (W, H)], fill=(10, 9, 22))
    return img.filter(ImageFilter.GaussianBlur(1.2))


def _sea(W: int, H: int) -> Image.Image:
    """海盐渐变(极简冷色)"""
    k = W / 1920.0
    img = _vgrad(W, H, [(0, (206, 228, 232)), (0.45, (128, 172, 192)), (1, (62, 96, 132))])
    d = ImageDraw.Draw(img, "RGBA")
    r = 480 * k
    d.ellipse([W * 0.70 - r, H * 0.18 - r, W * 0.70 + r, H * 0.18 + r], fill=(255, 255, 255, 26))
    return img


def _purple(W: int, H: int) -> Image.Image:
    """暮紫渐变(极简暖紫)"""
    k = W / 1920.0
    img = _vgrad(W, H, [(0, (246, 222, 238)), (0.4, (206, 168, 214)),
                        (0.75, (140, 112, 186)), (1, (86, 74, 148))])
    d = ImageDraw.Draw(img, "RGBA")
    r = 420 * k
    d.ellipse([W * 0.25 - r, H * 0.75 - r, W * 0.25 + r, H * 0.75 + r], fill=(255, 235, 250, 20))
    return img
