"""Render two share-card styles from the same confirmed schedule data."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from .model import DAYS
from .render import load_font
from .settings import atomic_bytes


CARD_STYLES = {"green": "墨绿日程", "simple": "简洁清单"}


def _lines(draw, text, font, width):
    for paragraph in text.splitlines() or [""]:
        start = 0
        while start < len(paragraph):
            end = start + 1
            while end < len(paragraph) and draw.textlength(paragraph[start:end + 1], font=font) <= width:
                end += 1
            if end < len(paragraph) and " " in paragraph[start:end]:
                end = max(start + 1, paragraph.rfind(" ", start, end) + 1)
            yield paragraph[start:end].strip()
            start = end


def render_schedule_card(draft, style):
    if style not in CARD_STYLES:
        raise ValueError("请选择有效的日程卡样式.")
    green = style == "green"
    page = "#f3f7ed" if green else "#ffffff"
    ink, muted = ("#23382f", "#476657") if green else ("#232a34", "#526071")
    accent = "#226348" if green else "#284481"
    width, edge = 880, 54
    x = width - edge * 2
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    def paragraph(text, size, color, *, bold=False, offset=0):
        font = load_font(size, bold)
        return [(line, font, color, offset) for line in _lines(probe, text, font, x - offset)]

    when = date.fromisoformat(draft["date"])
    time_label = f"{when.isoformat()}  {DAYS[when.weekday()]}  {draft['start']} - {draft['end']}"
    header = paragraph("小组日程安排", 20, "#b7dbca" if green else accent, bold=True)
    header += paragraph(draft["title"], 38, "#ffffff" if green else ink, bold=True)
    header += paragraph(time_label, 25, "#e4f4ec" if green else muted, bold=True)
    header += paragraph(f"地点  {draft['room'] or '待定'}", 22, "#e4f4ec" if green else muted)
    body = []
    if draft["notes"]:
        body.append(paragraph(draft["notes"], 24, muted))
    if draft["agenda"]:
        agenda = paragraph("现场议程", 25, accent, bold=True)
        position = datetime.fromisoformat(f"{draft['date']}T{draft['start']}")
        for row in draft["agenda"]:
            until = position + timedelta(minutes=row["minutes"])
            agenda += paragraph(f"{position:%H:%M}-{until:%H:%M}   {row['title']}", 23, ink)
            position = until
        body.append(agenda)
    if draft["prep"]:
        preparation = paragraph("会前分工", 25, accent, bold=True)
        for row in draft["prep"]:
            preparation += paragraph(f"{' / '.join(row['owners'])}  |  {row['title']}", 23, ink)
        body.append(preparation)

    def height(rows):
        return sum(font.size + 13 for _, font, _, _ in rows)

    header_height = height(header) + 90
    height_total = header_height + sum(height(rows) + 40 for rows in body) + 34
    if height_total > 16000:
        raise ValueError("日程卡内容过长. 请缩短长条目或使用小组代号.")
    image = Image.new("RGB", (width, height_total), page)
    draw = ImageDraw.Draw(image)
    if green:
        draw.rectangle((0, 0, width, header_height), fill="#123d2e")
    else:
        draw.rectangle((edge, header_height - 13, width - edge, header_height - 11), fill="#c9d3e3")

    def paint(rows, y):
        for line, font, color, offset in rows:
            draw.text((edge + offset, y), line, font=font, fill=color, anchor="lt")
            y += font.size + 13
        return y

    paint(header, 42)
    cursor = header_height + 24
    for rows in body:
        cursor = paint(rows, cursor) + 40
    return image


def write_schedule_card(draft, style, path):
    output = BytesIO()
    render_schedule_card(draft, style).save(output, "PNG")
    target = Path(path)
    atomic_bytes(target, output.getvalue())
    return target
