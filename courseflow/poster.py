"""A4 printable schedules and compact sharing cards, rendered locally."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from .model import Timetable
from .render import load_font, render_wallpaper


def export_poster(tt: Timetable, out, week: Optional[int] = None) -> Path:
    target = Path(out)
    if target.suffix.lower() not in {".png", ".pdf"}:
        raise ValueError("挂图输出格式应为 PNG 或 PDF.")
    image = render_wallpaper(tt, size=(3508, 2480), theme="paper", week=week).convert("RGB")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".pdf":
        image.save(target, "PDF", resolution=300.0, quality=95, title=tt.term or "CourseFlow 课表")
    else:
        image.save(target, dpi=(300, 300))
    return target


def export_share_card(tt: Timetable, out, week: Optional[int] = None) -> Path:
    schedule = render_wallpaper(tt, size=(1600, 1100), theme="light", week=week).convert("RGB")
    card = Image.new("RGB", (1680, 1300), "#eef2ff")
    card.paste(schedule, (40, 40))
    draw = ImageDraw.Draw(card)
    draw.text((70, 1190), "CourseFlow / 我的课程安排", font=load_font(34, True), fill="#263459")
    draw.text((70, 1240), "仅供查看, 最新调整以课程通知为准.", font=load_font(22), fill="#6b7891")
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    card.save(target)
    return target
