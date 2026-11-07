"""导出 .ics 日历.

每条实际课程展开成一个 VEVENT; 时间统一转成 UTC 写入, 手机/电脑日历
会按本地时区显示. 不依赖第三方日历库.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha1
from pathlib import Path
from typing import Optional

from .model import DAYS, Timetable
from .schedule import Occurrence, resolve_course
from .semester import SemesterCalendar, SemesterError


class CalendarError(ValueError):
    """日历导出条件不完整时抛的错."""


def _escape(text: str) -> str:
    value = str(text)
    value = value.replace("\\", "\\\\")
    value = value.replace(";", "\\;")
    value = value.replace(",", "\\,")
    value = value.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return value


def _fold_line(line: str) -> str:
    """按 RFC 5545 的 75 字节限制折行, 不切断 UTF-8 字符."""
    if len(line.encode("utf-8")) <= 75:
        return line
    chunks: list[str] = []
    current = ""
    current_bytes = 0
    limit = 75
    for char in line:
        char_bytes = len(char.encode("utf-8"))
        if current and current_bytes + char_bytes > limit:
            chunks.append(current)
            current = " " + char
            current_bytes = 1 + char_bytes
            limit = 74
        else:
            current += char
            current_bytes += char_bytes
    chunks.append(current)
    return "\r\n".join(chunks)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _uid(term: str, occ: Occurrence) -> str:
    raw = "|".join([
        term, occ.name, str(occ.week), str(occ.day),
        str(occ.start), str(occ.end), occ.room,
        str(occ.source_week), str(occ.course.day),
        str(occ.course.start), str(occ.course.end),
    ])
    return f"{sha1(raw.encode('utf-8')).hexdigest()[:20]}@courseflow"


def _event_lines(tt: Timetable, occ: Occurrence, calendar: SemesterCalendar,
                 reminder_minutes: int, stamp: str) -> list[str]:
    try:
        start, end = calendar.datetime_for(
            occ.week, occ.day, occ.start, occ.end,
        )
    except SemesterError as exc:
        raise CalendarError(f"'{occ.name}' 第 {occ.week} 周: {exc}") from exc

    span = f"{occ.start}-{occ.end}" if occ.start != occ.end else str(occ.start)
    description = f"{DAYS[occ.day]} 第 {occ.week} 周 第 {span} 节"
    if occ.room:
        description += f" · {occ.room}"

    lines = [
        "BEGIN:VEVENT",
        f"UID:{_uid(tt.term, occ)}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{_utc(start)}",
        f"DTEND:{_utc(end)}",
        f"SUMMARY:{_escape(occ.name)}",
        f"DESCRIPTION:{_escape(description)}",
        "STATUS:CONFIRMED",
    ]
    if occ.room:
        lines.append(f"LOCATION:{_escape(occ.room)}")
    if reminder_minutes > 0:
        lines.extend([
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_escape(occ.name)} 上课提醒",
            f"TRIGGER:-PT{int(reminder_minutes)}M",
            "END:VALARM",
        ])
    lines.append("END:VEVENT")
    return lines


def build_calendar(tt: Timetable, reminder_minutes: int = 15,
                   now: Optional[datetime] = None) -> str:
    """生成 .ics 文本; 周次或学期时间不完整时抛 CalendarError."""
    if reminder_minutes < 0:
        raise CalendarError("提醒分钟数不能为负数")
    try:
        calendar = SemesterCalendar.from_timetable(tt)
    except SemesterError as exc:
        raise CalendarError(str(exc)) from exc

    unknown: list[str] = []
    occurrences: list[Occurrence] = []
    for course in tt.courses:
        for occ in resolve_course(course, total_weeks=tt.weeks_total):
            if occ.week is None:
                unknown.append(course.name)
            else:
                occurrences.append(occ)
    if unknown:
        names = ", ".join(dict.fromkeys(unknown))
        raise CalendarError(f"这些课程周次无法识别, 请先修正: {names}")

    occurrences.sort(key=lambda o: (o.week, o.day, o.start, o.name))
    stamp_dt = now or datetime.now(timezone.utc)
    if stamp_dt.tzinfo is None:
        stamp_dt = stamp_dt.replace(tzinfo=timezone.utc)
    stamp = _utc(stamp_dt)

    name = tt.term or "课程表"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CourseFlow//CourseFlow//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
        f"X-WR-TIMEZONE:{_escape(calendar.tzid)}",
    ]
    for occ in occurrences:
        lines.extend(_event_lines(tt, occ, calendar, reminder_minutes, stamp))
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold_line(line) for line in lines) + "\r\n"


def write_calendar(tt: Timetable, path, reminder_minutes: int = 15,
                   now: Optional[datetime] = None) -> Path:
    target = Path(path)
    text = build_calendar(tt, reminder_minutes=reminder_minutes, now=now)
    with target.open("w", encoding="utf-8", newline="") as f:
        f.write(text)
    return target
