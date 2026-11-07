"""课表源文件(YAML)的读写与字段校验.

源文件是用户可以直接改的中间层. 这里负责把 YAML 变成 Timetable,
再把 Timetable 写回 YAML; 周次语义由 weeks.py 负责.
"""
from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

import yaml

from .model import DAYS, Change, Course, Timetable, parse_day, parse_periods
from .weeks import DEFAULT_TOTAL_WEEKS, parse_weeks
from .settings import atomic_text

SOURCE_HEADER = (
    "# CourseFlow 课表源文件 -- 用记事本就能改;改完可跑  term check  校对,再跑  term wallpaper  重新出图\n"
)

_TOP_KEYS = {
    "schema_version", "term", "semester_start", "weeks_total",
    "timezone", "period_times", "courses",
}
_COURSE_KEYS = {"name", "day", "periods", "weeks", "room", "skip", "changes"}
_CHANGE_KEYS = {"week", "day", "periods", "room", "target_week"}


class SourceFileError(ValueError):
    """课表源文件读不动时抛的错(错误文案会直接给用户看)."""


def _unknown_fields(mapping: dict, known: set[str]) -> dict:
    return {key: value for key, value in mapping.items() if key not in known}


def _warn_unknown(prefix: str, extra: dict, warn) -> None:
    if extra:
        keys = ", ".join(sorted(str(k) for k in extra))
        warn(f"{prefix}有无法识别的字段(已保留):{keys}")


def _parse_schema_version(value, warn) -> int:
    if value is None:
        return 2
    try:
        version = int(value)
    except (TypeError, ValueError):
        warn(f"schema_version 不是整数,已按 2 处理:{value!r}")
        return 2
    if version < 1:
        warn(f"schema_version 应大于 0,已按 2 处理:{value!r}")
        return 2
    return version


def _parse_semester_start(value, warn):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        warn(f"semester_start 应为 YYYY-MM-DD,已忽略:{value!r}")
        return None


def _parse_weeks_total(value, warn) -> int:
    if value is None or value == "":
        return DEFAULT_TOTAL_WEEKS
    try:
        total = int(value)
    except (TypeError, ValueError):
        warn(f"weeks_total 不是整数,已按 {DEFAULT_TOTAL_WEEKS} 处理:{value!r}")
        return DEFAULT_TOTAL_WEEKS
    if total < 1:
        warn(f"weeks_total 应大于 0,已按 {DEFAULT_TOTAL_WEEKS} 处理:{value!r}")
        return DEFAULT_TOTAL_WEEKS
    return total


def _parse_period_times(value, warn) -> dict[int, tuple[time, time]]:
    result: dict[int, tuple[time, time]] = {}
    if value is None or value == "":
        return result
    if not isinstance(value, dict):
        warn(f"period_times 应该是一个字典,已忽略:{value!r}")
        return result

    for key, raw in value.items():
        try:
            period = int(key)
        except (TypeError, ValueError):
            warn(f"period_times 的键应为节次数字,已跳过:{key!r}")
            continue
        if not 1 <= period <= 12:
            warn(f"period_times 的节次应在 1-12 内,已跳过:{period}")
            continue

        if isinstance(raw, (list, tuple)) and len(raw) == 2:
            parts = raw
        else:
            parts = str(raw).split("-")
        if len(parts) != 2:
            warn(f"period_times 第 {period} 节应为 08:00-08:45,已跳过:{raw!r}")
            continue
        try:
            start = time.fromisoformat(str(parts[0]).strip())
            end = time.fromisoformat(str(parts[1]).strip())
        except ValueError:
            warn(f"period_times 第 {period} 节时间无法识别,已跳过:{raw!r}")
            continue
        if end <= start:
            warn(f"period_times 第 {period} 节结束时间应晚于开始时间,已跳过:{raw!r}")
            continue
        result[period] = (start, end)

    return dict(sorted(result.items()))


def _parse_skip(value, warn, total_weeks: int) -> list[int]:
    """解析 skip 字段(停课周次).支持 [8, 9] / "8,9" / "8-9周" 等写法."""
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        if not value:
            return []
        value = ",".join(str(v) for v in value)
    weeks = parse_weeks(str(value), total_weeks=total_weeks)
    if weeks is None:
        warn(f"skip 无法识别,已忽略:{value!r}")
        return []
    return sorted(weeks)


def _parse_changes(value, warn, total_weeks: int) -> list[Change]:
    """解析 changes 字段(单次调整列表);有问题的条目跳过并记 warning."""
    out: list[Change] = []
    if value is None:
        return out
    if not isinstance(value, list):
        warn(f"changes 应该是一个列表,已忽略:{value!r}")
        return out

    seen_weeks: set[int] = set()
    for i, item in enumerate(value, 1):
        if not isinstance(item, dict):
            warn(f"changes 第 {i} 条不是字典,已跳过")
            continue

        extra = _unknown_fields(item, _CHANGE_KEYS)
        _warn_unknown(f"changes 第 {i} 条", extra, warn)

        wk = parse_weeks(item.get("week"), total_weeks=total_weeks)
        if wk is None or len(wk) != 1:
            warn(f"changes 第 {i} 条的 week 应为单周次(如 10),已跳过")
            continue
        week = min(wk)
        if not 1 <= week <= total_weeks:
            warn(f"changes 第 {i} 条的 week 超出学期范围,已跳过")
            continue
        if week in seen_weeks:
            warn(f"changes 第 {i} 条的 week {week} 重复,已跳过")
            continue

        target_week = None
        if item.get("target_week") is not None:
            target = parse_weeks(item["target_week"], total_weeks=total_weeks)
            if target is None or len(target) != 1 or not 1 <= min(target) <= total_weeks:
                warn(f"changes 第 {i} 条的 target_week 应为学期内的单周次,已跳过")
                continue
            target_week = min(target)

        day = None
        if item.get("day") is not None:
            day = parse_day(item.get("day"))
            if day is None:
                warn(f"changes 第 {i} 条的 day 无法识别,已跳过")
                continue

        periods = None
        if item.get("periods") is not None:
            periods = parse_periods(item.get("periods"))
            if periods is None:
                warn(f"changes 第 {i} 条的 periods 无法识别,已跳过")
                continue
            if periods[0] < 1 or periods[1] > 12:
                warn(f"changes 第 {i} 条的 periods 要在 1-12 节内"
                     f"(现在是 {periods[0]}-{periods[1]}),已跳过")
                continue

        room = str(item.get("room") or "").strip()
        if day is None and periods is None and not room and target_week is None:
            warn(f"changes 第 {i} 条没写明改什么(day / periods / room 至少一个),已跳过")
            continue

        seen_weeks.add(week)
        out.append(Change(
            week=week, day=day,
            start=periods[0] if periods else None,
            end=periods[1] if periods else None,
            room=room,
            extra=extra,
            target_week=target_week,
        ))
    return out


def load_source(path) -> Timetable:
    """读取课表源文件.遇到读不动的条目会收集到 warnings,不打断整体."""
    p = Path(path)
    if not p.exists():
        raise SourceFileError(f"没找到课表源文件:{p}")

    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise SourceFileError(f"课表源文件读不动:{p}\n  {exc}") from exc

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SourceFileError(f"课表源文件的格式有问题(YAML 解析失败):{p}\n  {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise SourceFileError("课表源文件的最外层应该是一个字典(term / courses 两节)")

    tt = Timetable(term=str(data.get("term") or "").strip())
    tt.schema_version = _parse_schema_version(
        data.get("schema_version"), lambda msg: tt.warnings.append(msg),
    )
    tt.semester_start = _parse_semester_start(
        data.get("semester_start"), lambda msg: tt.warnings.append(msg),
    )
    tt.weeks_total = _parse_weeks_total(
        data.get("weeks_total"), lambda msg: tt.warnings.append(msg),
    )
    tt.period_times = _parse_period_times(
        data.get("period_times"), lambda msg: tt.warnings.append(msg),
    )
    tt.timezone = str(data.get("timezone") or "Asia/Shanghai").strip() or "Asia/Shanghai"
    if tt.semester_start is not None and tt.semester_start.weekday() != 0:
        tt.warnings.append("semester_start 不是周一; 导出日历时请确认第 1 周从哪一天开始")

    unknown = _unknown_fields(data, _TOP_KEYS)
    tt.extra = unknown
    _warn_unknown("源文件顶层", unknown, lambda msg: tt.warnings.append(msg))

    raw_courses = data.get("courses")
    if raw_courses is None:
        raw_courses = []
    if not isinstance(raw_courses, list):
        raise SourceFileError("课表源文件的 courses 应该是一个列表")

    for i, item in enumerate(raw_courses, 1):
        if not isinstance(item, dict):
            tt.warnings.append(f"第 {i} 条不是字典,已跳过")
            continue
        name = str(item.get("name") or "").strip()
        day = parse_day(item.get("day") or "")
        periods = parse_periods(item.get("periods") or "")
        if not name or day is None or periods is None:
            tt.warnings.append(f"第 {i} 条缺 name / day / periods,已跳过({name or '无名'})")
            continue
        start = max(1, min(12, periods[0]))
        end = max(start, min(12, periods[1]))
        prefix = f"第 {i} 条({name or '无名'}):"
        extra = _unknown_fields(item, _COURSE_KEYS)
        _warn_unknown(prefix, extra, lambda msg: tt.warnings.append(msg))
        skip = _parse_skip(
            item.get("skip"), lambda msg: tt.warnings.append(prefix + msg), tt.weeks_total,
        )
        changes = _parse_changes(
            item.get("changes"), lambda msg: tt.warnings.append(prefix + msg), tt.weeks_total,
        )
        tt.courses.append(
            Course(
                name=name, day=day, start=start, end=end,
                room=str(item.get("room") or "").strip(),
                weeks=str(item.get("weeks") or "").strip(),
                skip=skip,
                changes=changes,
                extra=extra,
            )
        )
    return tt


def save_source(tt: Timetable, path) -> None:
    """把课表写回源文件(带一行使用说明;中文不转义;未知字段原样保留)."""
    courses = []
    for c in tt.sorted_courses():
        item: dict = dict(c.extra)
        item.update({
            "name": c.name,
            "day": c.day_name,
            "periods": f"{c.start}-{c.end}" if c.start != c.end else str(c.start),
            "weeks": c.weeks,
            "room": c.room,
        })
        if c.skip:
            item["skip"] = list(c.skip)
        if c.changes:
            item["changes"] = [_change_to_dict(ch) for ch in c.changes]
        courses.append(item)

    data = dict(tt.extra)
    data["schema_version"] = max(tt.schema_version, 3) if any(ch.target_week is not None for c in tt.courses for ch in c.changes) else tt.schema_version
    data["term"] = tt.term
    if tt.semester_start is not None:
        data["semester_start"] = tt.semester_start.isoformat()
    data["weeks_total"] = tt.weeks_total
    data["timezone"] = tt.timezone
    if tt.period_times:
        data["period_times"] = {
            str(period): f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
            for period, (start, end) in sorted(tt.period_times.items())
        }
    data["courses"] = courses
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    atomic_text(Path(path), SOURCE_HEADER + text)


def _change_to_dict(ch: Change) -> dict:
    """把一条单次调整写回源文件的字典形式(只写实际填了的字段)."""
    item: dict = dict(ch.extra)
    item["week"] = ch.week
    if ch.target_week is not None:
        item["target_week"] = ch.target_week
    if ch.day is not None:
        item["day"] = DAYS[ch.day]
    if ch.start is not None:
        item["periods"] = f"{ch.start}-{ch.end}" if ch.start != ch.end else str(ch.start)
    if ch.room:
        item["room"] = ch.room
    return item
