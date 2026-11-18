"""Interpret the common CourseFlow commands locally; ambiguous edits need input."""
from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
import re

from .agenda import local_today
from .model import parse_day
from .notice import NoticeIntent
from .semester import SemesterCalendar
from .weeks import _number

_NUM = r"[0-9零〇一二两三四五六七八九十百]+"
_DAY = r"(?:周|星期)[一二三四五六日天]"
_WEEK = rf"第\s*({_NUM})\s*周"
_PERIOD = rf"第?\s*({_NUM})(?:\s*[-~至到]\s*({_NUM}))?\s*(大节|小节|节)"
SHORTCODE = r"CF1\.[A-Za-z0-9_-]+\.[0-9a-fA-F]{8}"


def command_kind(text, file_count):
    if any(word in text for word in ("点格页", "点格链接")):
        return "point_grid"
    if (
        re.search(SHORTCODE, text)
        or any(word in text for word in ("空闲", "找时间", "忙闲", "组队", "成员"))
        or file_count > 1
    ):
        return "group_prepare"
    if file_count or formats_for(text) or wants_change(text):
        return "prepare"
    return "agenda"


def wants_change(text):
    return bool(re.search(r"调整?[到至]|调课|改[到至为成]|停课|取消.*课|换教室|移到|挪到", text))


def formats_for(text):
    lower = text.lower()
    names = []
    if "壁纸" in text:
        if "电脑" in text or "桌面" in text:
            names.append("desktop")
        if "手机" in text:
            names.append("phone")
        if not names:
            names.extend(("desktop", "phone"))
    for key, pattern in (
        ("yaml", r"yaml|yml|课表文件|导出(?:一份)?课表|另存"),
        ("ics", r"ics|日历"),
        ("pdf", r"pdf|打印"),
        ("png", r"png|挂图"),
    ):
        if re.search(pattern, lower):
            names.append(key)
    if "导出" in text and not names:
        names.append("yaml")
    return names


def week_for(text, timetable, *, default_delta=0):
    explicit = re.search(_WEEK, text)
    if explicit:
        week = _number(explicit[1])
    else:
        calendar = SemesterCalendar.from_timetable(timetable)
        today = local_today(timetable)
        delta = 2 if "下下周" in text else 1 if "下周" in text else -1 if "上周" in text else default_delta
        week = (today - calendar.start).days // 7 + 1 + delta
    if week is None or not 1 <= week <= timetable.weeks_total:
        raise ValueError("所查询周次不在学期内, 请明确写出第几周.")
    return week


def group_minimum(text):
    match = re.search(rf"(?:至少|连续)\s*({_NUM})(?:个)?\s*(大节|小节|节|分钟|小时)", text)
    if not match:
        return 2, 0
    number = _number(match[1])
    if not number or number < 1:
        raise ValueError("请提供有效的最短时长.")
    unit = match[2]
    if unit in ("分钟", "小时"):
        return 1, number * (60 if unit == "小时" else 1)
    return number * (2 if unit == "大节" else 1), 0


def period_span(text):
    match = re.search(_PERIOD, text)
    if not match:
        return ""
    first = _number(match[1])
    last = _number(match[2]) if match[2] else first
    if first is None or last is None:
        raise ValueError("请核对节次.")
    if match[3] == "大节":
        first, last = 2 * first - 1, 2 * last
    elif match[3] == "节" and not match[2]:
        raise ValueError("请说明是第几大节还是第几小节, 也可写具体节次范围, 如 3-4 节.")
    if not 1 <= first <= last <= 12:
        raise ValueError("节次必须在第 1-12 小节内.")
    return str(first) if first == last else f"{first}-{last}"


def adjust_intent(text, timetable):
    """Recognize the common move patterns. Other wording can use notification AI."""
    split = re.split(r"(?:调整?到|调整?至|调往|改到|改至|移动到|挪到|移到)", text, maxsplit=1)
    if len(split) != 2:
        return None
    source, destination = split
    destination = re.split(r"[\u3002\n]|再(?:生成|导出)|然后", destination, maxsplit=1)[0]
    day = re.search(_DAY, source)
    dest_day = re.search(_DAY, destination)
    source_span = period_span(source)
    target_span = period_span(destination)
    clock = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", destination)
    if not target_span and not clock:
        return None
    if not day and "今天" not in source and "明天" not in source and not re.search(_WEEK, source):
        return None
    today = local_today(timetable)
    relative_date = today + timedelta(days=1 if "明天" in source else 0)
    source_day = parse_day(day[0].replace("天", "日")) if day else relative_date.weekday() if "今天" in source or "明天" in source else None
    course = ""
    for item in sorted(timetable.courses, key=lambda item: len(item.name), reverse=True):
        if item.name in source:
            course = item.name
            break
    if not course:
        label = re.search(r"的\s*([^\uff0c\u3002:\uff1a]{1,40}?)课", source)
        if label and label[1] and label[1] != "那":
            course = label[1].strip()
    if not course and (source_day is None or not source_span):
        return None
    source_week = week_for(source, timetable, default_delta=int(relative_date.weekday() == 0 and relative_date > today))
    target_week = week_for(destination, timetable) if re.search(_WEEK, destination) or "下周" in destination else source_week
    target_day = parse_day(dest_day[0].replace("天", "日")) if dest_day else None
    if dest_day is not None and target_day is None:
        return None
    room = re.search(r"(?:地点|教室)(?:改为|改成|为|是|[:\uff1a])\s*([^,;\uff0c\u3002\uff1b]+)", destination)
    return asdict(NoticeIntent(
        course_name=course, source_week=source_week,
        source_day=source_day + 1 if source_day is not None else None, source_periods=source_span,
        target_week=target_week, target_day=target_day + 1 if target_day is not None else None,
        target_periods=target_span, target_time=f"{int(clock[1]):02d}:{clock[2]}" if clock else "",
        room=room[1].strip() if room else None, keep_day=target_day is None,
        keep_duration="时长可变" not in text,
    ))
