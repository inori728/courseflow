"""把课表渲染成壁纸(Pillow 纯本地:无 AI,不联网).

样式与效果预研定稿一致(C 方案):
- 微软雅黑,无文字特效;
- 课块不透明度 190(可读性优先);
- 文字颜色按块下的背景亮度自适应(亮底深字 / 暗底白字);
- 同格多课自动左右分栏.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageStat

from .backgrounds import make_background
from .model import DAYS, Timetable

REF_W = 1920                      # 参考稿宽度,其他尺寸按它等比缩放
BLOCK_ALPHA = 190                 # 课块不透明度(C 方案定稿值)
PHONE_SIZE = (1080, 2400)         # 手机竖屏版

COLORS = [
    (76, 110, 245), (18, 184, 134), (247, 103, 7), (190, 75, 219),
    (16, 152, 173), (232, 89, 12), (112, 72, 232), (47, 158, 68),
    (194, 37, 92), (25, 113, 194),
]

_REGULAR_FONTS = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]
_BOLD_FONTS = [
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]
_font_cache: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (max(int(size), 8), bool(bold))
    if key in _font_cache:
        return _font_cache[key]
    font = None
    for path in (_BOLD_FONTS if bold else _REGULAR_FONTS):
        if Path(path).exists():
            try:
                font = ImageFont.truetype(path, key[0])
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default(key[0])  # type: ignore[assignment]  # 兜底:系统没有任何中文字体时
    _font_cache[key] = font
    return font


def desktop_size() -> tuple[int, int]:
    """读当前屏幕分辨率(读不到就 1920×1080 保底)."""
    try:
        import ctypes
        try:  # 让读取不受系统缩放影响
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        w = int(ctypes.windll.user32.GetSystemMetrics(0))
        h = int(ctypes.windll.user32.GetSystemMetrics(1))
        if w > 0 and h > 0:
            return (w, h)
    except Exception:
        pass
    return (1920, 1080)


_FOLDERID_DESKTOP = (0xB4BFCC3A, 0xDB2C, 0x424C, (0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41))


def _desktop_dir() -> Path:
    """Windows 的桌面路径(顺带处理 OneDrive 重定向);其他系统回退 ~/Desktop."""
    try:
        import ctypes
        from ctypes import wintypes

        class _GUID(ctypes.Structure):
            _fields_ = [
                ("d1", wintypes.DWORD), ("d2", wintypes.WORD),
                ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8),
            ]

        d1, d2, d3, tail = _FOLDERID_DESKTOP
        g = _GUID(d1, d2, d3, (ctypes.c_ubyte * 8)(*tail))
        ptr = ctypes.c_wchar_p()
        hr = ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(ptr))
        if hr == 0 and ptr.value:
            path = Path(ptr.value)
            ctypes.windll.ole32.CoTaskMemFree(ptr)
            return path
    except Exception:
        pass
    return Path.home() / "Desktop"


def default_wallpaper_dir() -> Path:
    """壁纸默认输出目录:桌面\\课表壁纸"""
    return _desktop_dir() / "课表壁纸"


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """把图按"铺满不留白"裁剪到目标尺寸(居中裁剪)."""
    W, H = size
    scale = max(W / img.width, H / img.height)
    img2 = img.resize(
        (max(1, round(img.width * scale)), max(1, round(img.height * scale))),
        Image.Resampling.LANCZOS,
    )
    x = (img2.width - W) // 2
    y = (img2.height - H) // 2
    return img2.crop((x, y, x + W, y + H))


def _prepare_bg(size: tuple[int, int], background: str, bg_image=None, k: float = 1.0) -> Image.Image:
    if bg_image is not None:
        src = Image.open(bg_image).convert("RGB")
        bg = _cover(src, size)
        bg = bg.filter(ImageFilter.GaussianBlur(max(2.0, 6 * k)))
        bg = ImageEnhance.Brightness(bg).enhance(0.62)
        return bg
    return make_background(background, size)


def _text_w(d: ImageDraw.ImageDraw, text: str, font) -> float:
    bbox = d.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _fit(d: ImageDraw.ImageDraw, text: str, max_w: float, hi: int, lo: int,
         bold: bool = False) -> ImageFont.FreeTypeFont:
    for size in range(max(hi, lo), lo - 1, -1):
        f = load_font(size, bold)
        if _text_w(d, text, f) <= max_w:
            return f
    return load_font(lo, bold)


def _fit_down(d: ImageDraw.ImageDraw, text: str, hi: int, lo: int, max_w: float,
              bold: bool = False):
    """先按指定字号尝试,放不下再往小缩.返回 (font, fits)."""
    f = _fit(d, text, max_w, hi, lo, bold=bold)
    return f, _text_w(d, text, f) <= max_w


def _layout_name(d: ImageDraw.ImageDraw, text: str, max_w: float,
                 one_hi: int, one_lo: int, multi_hi: int, multi_lo: int,
                 ell: int) -> tuple[list[str], ImageFont.FreeTypeFont]:
    """课名排版:尽量一行 → 两行 → 省略号."""
    f = _fit(d, text, max_w, one_hi, one_lo, bold=True)
    if _text_w(d, text, f) <= max_w:
        return [text], f
    for size in range(multi_hi, multi_lo - 1, -1):
        f2 = load_font(size, True)
        mid = max(2, len(text) // 2)
        for i in range(max(2, mid - 3), min(len(text) - 1, mid + 4)):
            if _text_w(d, text[:i], f2) <= max_w and _text_w(d, text[i:], f2) <= max_w:
                return [text[:i], text[i:]], f2
    f3 = load_font(ell, True)
    t = text
    while len(t) > 1 and _text_w(d, t + "...", f3) > max_w:
        t = t[:-1]
    return [t + "..."], f3


def render_wallpaper(tt: Timetable, size=(1920, 1080), background: str = "dusk",
                     bg_image=None, block_alpha: int = BLOCK_ALPHA,
                     text_mode: str = "white") -> Image.Image:
    """把一张课表渲染成图片(返回 PIL Image,不落盘).

    block_alpha:课块不透明度(0~255),默认 190(预研 C 方案定稿值).
    text_mode:white = 统一白字(默认,色块整体压深一点保对比);auto = 字色随背景亮度自适应.
    """
    W, H = size
    k = W / REF_W

    def s(v: float, lo: int) -> int:
        """按宽度缩放一个数值,附带最小保底"""
        return max(int(round(v * k)), lo)

    margin = s(90, 24)
    top = s(150, 68)
    bottom = s(70, 40)
    gutter = s(64, 30)

    f_title = load_font(s(34, 24), True)
    f_sub = load_font(s(20, 13))
    f_day = load_font(s(24, 16), True)
    f_row = load_font(s(18, 12))

    bg = _prepare_bg(size, background, bg_image, k)

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)

    # -- 顶部:标题 + 一行小字 --
    today = datetime.now().strftime("%Y-%m-%d")
    title = f"{tt.term} · 我的课表" if tt.term else "我的课表"
    d.text((margin, s(46, 22)), title, font=f_title, fill=(255, 255, 255, 255))
    d.text((margin, s(98, 50)), f"共 {len(tt)} 条课程 · 由 CourseFlow 生成 · {today}",
           font=f_sub, fill=(255, 255, 255, 232))

    # -- 表格区 --
    grid_x0 = margin + gutter
    grid_y0 = top + s(56, 26)
    grid_x1 = W - margin
    grid_y1 = H - bottom
    col_w = (grid_x1 - grid_x0) / 7.0
    row_h = (grid_y1 - grid_y0) / 12.0
    if H >= W * 1.5:
        # 竖屏(手机)版:限制行高--课块别又细又长,表格下方留点背景透气
        row_h = min(row_h, col_w * 0.95)
        grid_y1 = grid_y0 + row_h * 12.0
    line_a = 55 if k >= 0.8 else 75  # 小尺寸(手机版)的网格线画明显一点

    d.rounded_rectangle(
        [margin - s(6, 3), top - s(6, 3), W - margin + s(16, 8), grid_y1 + s(16, 8)],
        radius=s(18, 8), fill=(255, 255, 255, 30),
    )
    for i, day in enumerate(DAYS):
        cx = grid_x0 + i * col_w + col_w / 2
        bbox = d.textbbox((0, 0), day, font=f_day)
        d.text((cx - (bbox[2] - bbox[0]) / 2, top + s(8, 4)), day,
               font=f_day, fill=(255, 255, 255, 255))
    for r in range(12):
        y = grid_y0 + r * row_h
        bbox = d.textbbox((0, 0), str(r + 1), font=f_row)
        d.text((margin + gutter / 2 - (bbox[2] - bbox[0]) / 2,
                y + row_h / 2 - (bbox[3] + bbox[1]) / 2), str(r + 1),
               font=f_row, fill=(255, 255, 255, 220))
        d.line([(grid_x0, y), (grid_x1, y)], fill=(255, 255, 255, line_a), width=1)
    d.line([(grid_x0, grid_y1), (grid_x1, grid_y1)], fill=(255, 255, 255, line_a), width=1)
    for i in range(8):
        x = grid_x0 + i * col_w
        d.line([(x, grid_y0), (x, grid_y1)], fill=(255, 255, 255, line_a), width=1)

    # -- 课块 --(同名课用同一种颜色)
    courses = tt.sorted_courses()
    palette = COLORS
    if text_mode == "white":  # 统一白字时,把色块整体压深一点,保证对比
        palette = [tuple(int(v * 0.80) for v in c) for c in COLORS]
    color_of = {
        name: palette[i % len(palette)]
        for i, name in enumerate(dict.fromkeys(c.name for c in courses))
    }
    block_alpha = max(0, min(255, int(block_alpha)))
    a = block_alpha / 255.0
    center_text = H >= W * 1.5  # 竖屏(手机)版:块很高,文字垂直居中更好看

    for c in courses:
        # 同格多课 → 左右分栏
        same = [o for o in courses if o.day == c.day and not (o.end < c.start or c.end < o.start)]
        same_sorted = sorted(same, key=lambda o: (o.start, o.name))
        lane = same_sorted.index(c)
        n = len(same_sorted)

        colx = grid_x0 + c.day * col_w
        inner = col_w - s(6, 3)
        lw = inner / n
        x0 = colx + s(3, 2) + lane * lw + s(1.5, 1)
        x1 = colx + s(3, 2) + (lane + 1) * lw - s(1.5, 1)
        y0 = grid_y0 + (c.start - 1) * row_h + s(3, 2)
        y1 = grid_y0 + c.end * row_h - s(3, 2)

        tint = color_of[c.name]
        d.rounded_rectangle([x0, y0, x1, y1], radius=s(10, 5), fill=tint + (block_alpha,))
        d.rounded_rectangle([x0, y0, x1, y1], radius=s(10, 5), outline=(255, 255, 255, 100), width=1)

        # 文字颜色自适应:把"课块叠在背景上"的颜色估出来,亮就深字,暗就白字
        region = bg.crop((int(x0), int(y0), int(x1), int(y1)))
        avg = ImageStat.Stat(region).mean
        comp = [tint[i] * a + avg[i] * (1 - a) for i in range(3)]
        lum = 0.299 * comp[0] + 0.587 * comp[1] + 0.114 * comp[2]
        if text_mode == "white":
            name_c, sub_c, wk_c = (255, 255, 255, 255), (255, 255, 255, 250), (248, 250, 255, 242)
        elif lum > 135:
            name_c, sub_c, wk_c = (30, 33, 42, 255), (48, 53, 70, 250), (52, 58, 76, 246)
        else:
            name_c, sub_c, wk_c = (255, 255, 255, 255), (255, 255, 255, 250), (248, 250, 255, 242)

        maxw = (x1 - x0) - s(20, 10)
        left = x0 + s(10, 5)
        lines, nf = _layout_name(
            d, c.name, maxw,
            one_hi=s(20, 18), one_lo=s(13, 14),
            multi_hi=s(15, 14), multi_lo=s(11, 12), ell=s(12, 12),
        )
        rows: list[tuple[str, ImageFont.FreeTypeFont, tuple]] = [
            (ln, nf, name_c) for ln in lines
        ]
        sub = f"{c.room} · {c.weeks}" if (c.room and c.weeks) else (c.room or c.weeks)
        if sub:
            f_bs, fits = _fit_down(d, sub, s(15, 14), s(10, 12), maxw, bold=True)
            if fits:
                rows.append((sub, f_bs, sub_c))
            else:
                if c.room:
                    rows.append((c.room, load_font(s(15, 13), True), sub_c))
                if c.weeks:
                    rows.append(("· " + c.weeks, load_font(s(13, 12), True), wk_c))

        gap = s(3, 2)
        total_h = sum(f.size for _, f, _ in rows) + gap * (len(rows) - 1)
        if center_text:
            ty = y0 + max(s(8, 4), (y1 - y0 - total_h) / 2)
        else:
            ty = y0 + s(8, 4)
        for text, font, color in rows:
            d.text((left, ty), text, font=font, fill=color)
            ty += font.size + gap

    return Image.alpha_composite(bg.convert("RGBA"), ov)


def render_to_files(tt: Timetable, out_dir=None, which: str = "both",
                    background: str = "dusk", bg_image=None,
                    block_alpha: int = BLOCK_ALPHA) -> list[tuple[Path, tuple[int, int]]]:
    """出图并存到磁盘.返回 [(路径, 尺寸), ...]."""
    out = Path(out_dir) if out_dir else default_wallpaper_dir()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")

    jobs: list[tuple[str, tuple[int, int]]] = []
    if which in ("both", "desktop"):
        jobs.append(("电脑", desktop_size()))
    if which in ("both", "phone"):
        jobs.append(("手机", PHONE_SIZE))

    results: list[tuple[Path, tuple[int, int]]] = []
    for label, size in jobs:
        img = render_wallpaper(tt, size=size, background=background, bg_image=bg_image,
                               block_alpha=block_alpha)
        path = out / f"课表壁纸_{label}_{stamp}.png"
        img.convert("RGB").save(path)
        results.append((path, size))
    return results
