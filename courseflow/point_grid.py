"""Export a standalone fill-in page with only shared calendar defaults."""
from __future__ import annotations

from pathlib import Path
import json

from .semester import _tzinfo
from .settings import atomic_text

DEFAULTS_TAG = '<script id="courseflow-defaults" type="application/json">{}</script>'


def resource_path():
    return Path(__file__).resolve().parent / "data" / "availability.html"


def page_defaults(timetable=None, members=(), week=1):
    if isinstance(week, bool) or not isinstance(week, (int, str)) or (isinstance(week, str) and not week.strip().isdigit()):
        raise ValueError("查询周次应在 1-104 之间.")
    week = int(week)
    if not 1 <= week <= 104:
        raise ValueError("查询周次应在 1-104 之间.")
    start, clocks, timezone = None, {}, "Asia/Shanghai"
    if members:
        start = members[0].semester_start
        timezone = members[0].timezone
        clocks = next((member.period_times for member in members if member.period_times), {})
        if any(member.timezone != timezone for member in members):
            raise ValueError("成员时区不一致, 请统一后再分享点格页.")
        if any(member.period_times and member.period_times != clocks for member in members):
            raise ValueError("成员作息不一致, 请核对后再分享点格页.")
    elif timetable is not None:
        start, clocks, timezone = timetable.semester_start, timetable.period_times, timetable.timezone
    if start is not None and start.weekday() != 0:
        raise ValueError("学期第 1 周的起始日期必须是周一.")
    _tzinfo(timezone)
    return {
        "start": start.isoformat() if start else "", "week": week,
        "period_times": {str(period): f"{first.strftime('%H:%M')}-{last.strftime('%H:%M')}"
                         for period, (first, last) in sorted(clocks.items())},
        "timezone": timezone,
    }


def export_page(out, timetable=None, members=(), week=1):
    target = Path(out)
    if target.suffix.lower() not in {".html", ".htm"}:
        raise ValueError("点格页请保存为 .html 文件, 再发送给成员.")
    template = resource_path()
    if target.resolve() == template.resolve():
        raise ValueError("请选择其他保存位置, 避免覆盖内置点格页.")
    defaults = page_defaults(timetable, members, week)
    content = template.read_text(encoding="utf-8")
    if content.count(DEFAULTS_TAG) != 1:
        raise ValueError("点格页资源不完整, 请检查安装包.")
    raw = json.dumps(defaults, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c").replace("&", "\\u0026")
    atomic_text(target, content.replace(DEFAULTS_TAG, DEFAULTS_TAG.replace("{}", raw)))
    return target
