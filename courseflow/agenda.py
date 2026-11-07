"""Today/tomorrow/week views use the same resolved occurrences as calendars."""
from __future__ import annotations

from datetime import date, datetime, timezone

from .model import Timetable
from .schedule import resolve_timetable
from .semester import SemesterCalendar, _tzinfo


def local_today(tt: Timetable, now=None) -> date:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_tzinfo(tt.timezone)[0]).date()


def week_number(tt: Timetable, day=None) -> int:
    calendar = SemesterCalendar.from_timetable(tt)
    return ((day or local_today(tt)) - calendar.start).days // 7 + 1


def agenda_text(tt: Timetable, day=None) -> str:
    calendar = SemesterCalendar.from_timetable(tt)
    day = day or local_today(tt)
    week = week_number(tt, day)
    occurrences = resolve_timetable(tt, tt.weeks_total)
    unknown = list(dict.fromkeys(occ.name for occ in occurrences if occ.week is None))
    dated = [(calendar.date_for(occ.week, occ.day), occ) for occ in occurrences
             if occ.week is not None and 1 <= occ.week <= tt.weeks_total]
    dated.sort(key=lambda item: (item[0], item[1].start, item[1].name))
    today = [occ for current, occ in dated if current == day]
    lines = [f"{day.isoformat()} / 第 {week} 周" if 1 <= week <= tt.weeks_total else f"{day.isoformat()} / 当前不在本学期范围"]
    for occ in today:
        clock = ""
        if occ.start in tt.period_times and occ.end in tt.period_times:
            clock = f" {tt.period_times[occ.start][0].strftime('%H:%M')}-{tt.period_times[occ.end][1].strftime('%H:%M')}"
        lines.append(f"- {occ.start}-{occ.end} 节{clock} {occ.name} @{occ.room or '未填地点'}")
    if not today:
        lines.append("今天没有已确认的课程.")
        upcoming = next(((current, occ) for current, occ in dated if current > day), None)
        if upcoming:
            current, occ = upcoming
            lines.append(f"下次课程: {current.isoformat()} {occ.slot_text()} {occ.name} @{occ.room}")
    if unknown:
        lines.append("周次待确认, 未计入上述结果: " + ", ".join(unknown))
    return "\n".join(lines)
