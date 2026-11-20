"""Local wallpaper rendering with separate desktop and phone layouts."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .backgrounds import make_background, normalize as normalize_background
from .model import Course, DAYS, Timetable
from .schedule import resolve_timetable

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


def _prepare_bg(size, background, bg_image, layout, blur, brightness):
    if bg_image is None:
        return make_background(background, size, layout)
    with Image.open(bg_image) as source:
        bg = ImageOps.fit(source.convert("RGB"), size, Image.Resampling.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(max(0.0, blur * size[0] / REF_W)))
    return ImageEnhance.Brightness(bg).enhance(brightness)


def _wrap(draw, text, font, width, max_lines):
    remaining = " ".join(text.split())
    lines = []
    while remaining and len(lines) < max_lines:
        count = 1
        if draw.textlength(remaining, font=font) <= width:
            lines.append(remaining)
            break
        suffix = "..." if len(lines) + 1 == max_lines else ""
        while count < len(remaining) and draw.textlength(remaining[:count + 1] + suffix, font=font) <= width:
            count += 1
        split = remaining.rfind(" ", 0, count + 1)
        if split > count * .6:
            count = split
        lines.append(remaining[:count].rstrip() + suffix)
        remaining = remaining[count:].lstrip()
    return lines


def _course_lists(tt, week):
    if week is None:
        return tt.sorted_courses(), False
    courses = []
    unknown = False
    for occ in resolve_timetable(tt, tt.weeks_total):
        if occ.week not in {None, week}:
            continue
        unknown = unknown or occ.week is None
        courses.append(Course(occ.name, occ.day, occ.start, occ.end, occ.room,
                              "周次待确认" if occ.week is None else f"第 {week} 周"))
    return sorted(courses, key=lambda course: (course.day, course.start, course.name)), unknown


def _card_board(width, courses, rows, title, subtitle, palette, alpha, white, *, style, density=1.0):
    phone = style == "phone"
    scale = width / (760 if phone else 920) * density

    def unit(value, minimum=1):
        return max(minimum, round(value * scale))

    pad, gutter = unit(21), unit(13)
    title_font = load_font(unit(35, 12), True)
    sub_font = load_font(unit(18, 9))
    day_font = load_font(unit(24, 10), True)
    course_font = load_font(unit(23 if phone else 18, 9), True)
    meta_font = load_font(unit(17 if phone else 14, 8))
    ink, muted = "#203449", "#435267"
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    title_lines = _wrap(probe, title, title_font, width - 2 * pad, 2)
    subtitle_lines = _wrap(probe, subtitle, sub_font, width - 2 * pad, 2)
    header_height = (len(title_lines) * (title_font.size + unit(5))
                     + len(subtitle_lines) * (sub_font.size + unit(4)) + unit(14)) if title else 0
    day_courses = [[course for course in courses if course.day == day] for day in range(7)]
    positions = []
    y = pad + header_height
    for row in rows:
        sunday = phone and len(row) == 1
        columns = 2 if sunday else len(row)
        col = (width - 2 * pad - (columns - 1) * gutter) // columns
        content_top = y + day_font.size + unit(8)
        cursors = [content_top] * columns
        for index, day in enumerate(row):
            x = pad + index * (col + gutter)
            positions.append(("day", DAYS[day], x, y, width - pad if sunday else x + col))
            if not day_courses[day]:
                positions.append(("empty", "无课", x, content_top, x + col))
                cursors[index] += meta_font.size + unit(9)
            for number, course in enumerate(day_courses[day]):
                lane = number % 2 if sunday else index
                x = pad + lane * (col + gutter)
                meta = f"{course.start}-{course.end} 节" if course.start != course.end else f"{course.start} 节"
                meta = " · ".join(filter(None, (meta, course.room, course.weeks)))
                names = _wrap(probe, course.name, course_font, col - unit(23), 2)
                details = _wrap(probe, meta, meta_font, col - unit(23), 2)
                height = (len(names) * (course_font.size + unit(2))
                          + len(details) * (meta_font.size + unit(2)) + unit(10))
                positions.append(("course", course.name, x, cursors[lane], x + col, height, names, details))
                cursors[lane] += height + unit(5)
        y = max(cursors) + unit(8)
    height = y + pad
    board = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(board)
    fill = (248, 247, 247, 172) if phone else (250, 248, 238, 236)
    draw.rounded_rectangle((1, 1, width - 2, height - 2), radius=unit(23 if phone else 13),
                           fill=fill, outline=(255, 255, 255, 215), width=unit(1))
    if title:
        y = pad
        for lines, font, color in ((title_lines, title_font, ink), (subtitle_lines, sub_font, muted)):
            for line in lines:
                draw.text((pad, y), line, font=font, fill=color, anchor="lt")
                y += font.size + unit(5)
        draw.line((pad, y + unit(3), width - pad, y + unit(3)), fill="#afbfc9", width=1)
    for kind, name, x, y, right, *details in positions:
        if kind == "day":
            draw.text((x, y), name, font=day_font, fill=ink, anchor="lt")
            left = x + draw.textlength(name, font=day_font) + unit(10)
            if left < right:
                draw.line((left, y + day_font.size // 2, right, y + day_font.size // 2), fill="#a9b4bf", width=1)
        elif kind == "empty":
            draw.text((x, y + unit(2)), name, font=meta_font, fill=muted, anchor="lt")
        else:
            item_height, names, notes = details
            color = palette[name]
            tone = tuple(round(value * .15 + 255 * .85) for value in color)
            if white:
                tone = tuple(round(value * .40 + 18) for value in color)
            draw.rounded_rectangle((x, y, right, y + item_height), radius=unit(8),
                                   fill=(*tone, alpha), outline=(*color, max(75, alpha // 2)), width=1)
            draw.rounded_rectangle((x + unit(3), y + unit(6), x + unit(5), y + item_height - unit(6)),
                                   radius=unit(2), fill=(*color, 245))
            line_y = y + unit(5)
            for lines, font, foreground in ((names, course_font, "#ffffff" if white else ink),
                                             (notes, meta_font, "#f1f5fb" if white else muted)):
                for line in lines:
                    draw.text((x + unit(10), line_y), line, font=font, fill=foreground, anchor="lt")
                    line_y += font.size + unit(2)
    return board


def _desktop_layout(bg, cards, title, subtitle, palette, alpha, white, top_safe, bottom_safe, wall):
    width, height = bg.size
    left, top = int(width * .025), int(height * max(.11, top_safe))
    board_width = int(width * (.55 if wall else .62))
    floor = max(20, int(height * (1 - max(.045, bottom_safe))) - top)
    rows = ((0, 1, 2), (3, 4, 5, 6))
    board = _card_board(board_width, cards, rows, title, subtitle, palette, alpha, white, style="desktop")
    if board.height > floor:
        board = _card_board(board_width, cards, rows, title, subtitle, palette, alpha, white,
                            style="desktop", density=max(.55, floor / board.height))
    if board.height > floor:
        board = ImageOps.contain(board, (board.width, floor), Image.Resampling.LANCZOS)
    if wall and board.height > 80:
        bw, bh = board.size
        # Small change in angle to align the panel with the classroom wall.
        shift = max(2, round(bw * .012))
        board = board.transform((bw + shift, bh + shift), Image.Transform.QUAD,
                                (-shift, 0, 0, bh, bw, bh + shift, bw + shift, -shift),
                                Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0))
    bg.alpha_composite(board, (left, top))


def _phone_layout(bg, cards, title, subtitle, palette, alpha, white, top_safe, bottom_safe):
    width, height = bg.size
    left, top = int(width * .05), int(height * max(.115, top_safe))
    board_width = width - 2 * left
    title_font = load_font(round(width * .05), True)
    sub_font = load_font(round(width * .026))
    draw = ImageDraw.Draw(bg)
    title_lines = _wrap(draw, title, title_font, board_width, 2)
    subtitle_lines = _wrap(draw, subtitle, sub_font, board_width, 2)
    header_height = len(title_lines) * (title_font.size + 6) + len(subtitle_lines) * (sub_font.size + 5)
    y = top
    foreground = "#1c293b"
    if bg.convert("L").crop((left, top, width - left, min(height, top + header_height))).resize((1, 1)).getpixel((0, 0)) < 105:
        foreground = "#ffffff"
    for lines, font in ((title_lines, title_font), (subtitle_lines, sub_font)):
        for line in lines:
            draw.text((width // 2, y), line, font=font, fill=foreground, anchor="mt")
            y += font.size + 6
    y += int(height * .012)
    rows = ((0, 1), (2, 3), (4, 5), (6,))
    room = max(24, int(height * (1 - max(.06, bottom_safe))) - y)
    preferred = max(24, int(height * .65) - y)
    board = _card_board(board_width, cards, rows, "", "", palette, alpha, white, style="phone")
    if board.height > preferred:
        board = _card_board(board_width, cards, rows, "", "", palette, alpha, white, style="phone",
                            density=max(.72, preferred / board.height))
    if board.height > room:
        board = ImageOps.contain(board, (board.width, room), Image.Resampling.LANCZOS)
    bg.alpha_composite(board, ((width - board.width) // 2, y))


def render_wallpaper(tt: Timetable, size=(1920, 1080), background: str = "dusk",
                     bg_image=None, block_alpha: int = BLOCK_ALPHA,
                     text_mode: str = "auto", week: Optional[int] = None,
                     theme: str = "dark", blur: float = 6.0, brightness: float = 0.62,
                     top_safe: float = 0.0, bottom_safe: float = 0.0, layout=None) -> Image.Image:
    """Render the actual course data as a desktop board or a phone card layout."""
    width, height = size
    if width < 640 or height < 480:
        raise ValueError("图片尺寸至少为 640x480.")
    if theme not in {"dark", "light", "paper"}:
        raise ValueError("主题应为 dark / light / paper.")
    if week is not None and not 1 <= week <= tt.weeks_total:
        raise ValueError("周次超出学期范围.")
    if not 0 <= top_safe <= .3 or not 0 <= bottom_safe <= .3:
        raise ValueError("安全边距比例应在 0-0.3 之间.")
    layout = layout or ("phone" if height > width else "desktop")
    if layout not in {"desktop", "phone"}:
        raise ValueError("请选择电脑或手机壁纸.")
    cards, unknown = _course_lists(tt, week)
    view = f"第 {week} 周" if week is not None else "学期总览"
    title = tt.term or "我的课表"
    subtitle = view + (" · 含周次待确认课程" if unknown else "")
    palette = {name: COLORS[index % len(COLORS)] for index, name in enumerate(dict.fromkeys(c.name for c in cards))}
    alpha = max(0, min(255, int(block_alpha)))
    white = text_mode == "white" and theme == "dark"
    if theme == "paper":
        bg = Image.new("RGBA", size, "white")
    else:
        bg = _prepare_bg(size, background, bg_image, layout, blur, brightness)
        if theme == "light":
            bg = Image.blend(bg, Image.new("RGB", size, "#f4f6ff"), .20)
        bg = bg.convert("RGBA")
    if layout == "phone":
        _phone_layout(bg, cards, title, subtitle, palette, alpha, white, top_safe, bottom_safe)
    else:
        wall = normalize_background(background) == "sea" and bg_image is None and theme != "paper" and width / height > 1.55
        _desktop_layout(bg, cards, title, subtitle, palette, alpha, white, top_safe, bottom_safe, wall)
    return bg

def wallpaper_size(layout):
    return PHONE_SIZE if layout == "phone" else desktop_size()


def render_to_files(tt: Timetable, out_dir=None, which: str = "both",
                    background: str = "dusk", bg_image=None,
                    block_alpha: int = BLOCK_ALPHA, week: Optional[int] = None,
                    theme: str = "dark", **options) -> list[tuple[Path, tuple[int, int]]]:
    """出图并存到磁盘.返回 [(路径, 尺寸), ...]."""
    out = Path(out_dir) if out_dir else default_wallpaper_dir()
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")

    jobs: list[tuple[str, str, tuple[int, int]]] = []
    if which in ("both", "desktop"):
        jobs.append(("desktop", "电脑", wallpaper_size("desktop")))
    if which in ("both", "phone"):
        jobs.append(("phone", "手机", wallpaper_size("phone")))

    results: list[tuple[Path, tuple[int, int]]] = []
    for layout, label, size in jobs:
        img = render_wallpaper(tt, size=size, background=background, bg_image=bg_image,
                               block_alpha=block_alpha, week=week, theme=theme, layout=layout, **options)
        view = f"_第{week}周" if week is not None else ""
        path = out / f"课表壁纸_{label}{view}_{stamp}.png"
        img.convert("RGB").save(path)
        results.append((path, size))
    return results
