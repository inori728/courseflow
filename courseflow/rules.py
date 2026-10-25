"""放假与调休提醒.

规则引擎只负责"提醒", 不自动修改课表:
- 法定节假日: 列出放假日以及原课表上受影响的课程;
- 调休上班日: 提醒用户确认按哪一天的课表执行;
- 用户确认后再自己改 skip / changes.

在线更新放假数据(term update-holidays)属于可选能力, 本轮先只使用内置数据.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from .model import Timetable
from .schedule import resolve_course
from .semester import SemesterCalendar, SemesterError

_DATA_DIR = Path(__file__).with_name("data")
_BUILTIN_TEMPLATE = "holidays-{year}.json"


class HolidayDataError(ValueError):
    """放假数据无法读取或格式不正确."""


@dataclass(frozen=True)
class HolidayDay:
    name: str
    date: date
    is_off: bool


@dataclass
class HolidayData:
    year: int
    days: list[HolidayDay]
    source: str


@dataclass(frozen=True)
class HolidaySpan:
    name: str
    start: date
    end: date
    is_off: bool
    affected: tuple[str, ...] = ()

    def describe(self) -> str:
        if self.start == self.end:
            span = self.start.isoformat()
        else:
            span = f"{self.start.isoformat()} 至 {self.end.isoformat()}"
        if self.is_off:
            text = f"{self.name}: {span} 放假"
            if self.affected:
                text += f"; 原课表有 {len(self.affected)} 次课, 请确认是否手动停课"
            else:
                text += "; 原课表没有课"
            return text
        return f"{self.name}: {span} 调休上班日, 请确认按哪一天课表执行"


@dataclass
class HolidayReport:
    year: int
    notices: list[HolidaySpan]
    warnings: list[str]

    def lines(self) -> list[str]:
        out: list[str] = []
        for notice in self.notices:
            out.append(f"- {notice.describe()}")
            for item in notice.affected:
                out.append(f"  - {item}")
        return out


def _read_holiday_file(path: Path, expected_year: int) -> HolidayData:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HolidayDataError(f"放假数据读不动:{path}") from exc
    return _parse_payload(payload, expected_year, str(path))


def _parse_payload(payload, expected_year: int, source: str) -> HolidayData:
    if not isinstance(payload, dict):
        raise HolidayDataError(f"放假数据格式不对:{source}")
    try:
        year = int(payload.get("year"))
    except (TypeError, ValueError) as exc:
        raise HolidayDataError(f"放假数据缺少年份:{source}") from exc
    if year != expected_year:
        raise HolidayDataError(f"放假数据年份不匹配:{source}({year} != {expected_year})")

    raw_days = payload.get("days")
    if not isinstance(raw_days, list):
        raise HolidayDataError(f"放假数据缺少 days 列表:{source}")

    days: list[HolidayDay] = []
    for i, item in enumerate(raw_days, 1):
        if not isinstance(item, dict):
            raise HolidayDataError(f"放假数据第 {i} 条格式不对:{source}")
        name = str(item.get("name") or "").strip()
        raw_date = item.get("date")
        is_off = item.get("isOffDay")
        if not name or not isinstance(is_off, bool):
            raise HolidayDataError(f"放假数据第 {i} 条缺少 name / isOffDay:{source}")
        try:
            day = date.fromisoformat(str(raw_date))
        except ValueError as exc:
            raise HolidayDataError(f"放假数据第 {i} 条日期不对:{raw_date!r}") from exc
        if day.year != year:
            raise HolidayDataError(f"放假数据第 {i} 条日期不在 {year} 年:{day}")
        days.append(HolidayDay(name=name, date=day, is_off=is_off))
    return HolidayData(year=year, days=days, source=source)


def load_holidays(year: int) -> Optional[HolidayData]:
    """读取内置放假数据; 没有对应年份时返回 None."""
    path = _DATA_DIR / _BUILTIN_TEMPLATE.format(year=year)
    if not path.exists():
        return None
    return _read_holiday_file(path, year)


def _group_spans(days: list[HolidayDay]) -> list[HolidaySpan]:
    spans: list[HolidaySpan] = []
    for day in sorted(days, key=lambda d: d.date):
        if (
            spans
            and spans[-1].name == day.name
            and spans[-1].is_off == day.is_off
            and spans[-1].end + timedelta(days=1) == day.date
        ):
            previous = spans[-1]
            spans[-1] = HolidaySpan(
                name=previous.name, start=previous.start, end=day.date,
                is_off=previous.is_off,
            )
        else:
            spans.append(HolidaySpan(
                name=day.name, start=day.date, end=day.date, is_off=day.is_off,
            ))
    return spans


def holiday_report(tt: Timetable, year: Optional[int] = None) -> HolidayReport:
    """生成放假 / 调休提醒; 不修改 Timetable."""
    fallback_year = year or (tt.semester_start.year if tt.semester_start else date.today().year)
    try:
        calendar = SemesterCalendar.from_timetable(tt)
    except SemesterError as exc:
        return HolidayReport(year=fallback_year, notices=[], warnings=[str(exc)])

    term_start = calendar.start
    term_end = calendar.date_for(tt.weeks_total, 6)
    years = [year] if year else list(range(term_start.year, term_end.year + 1))

    warnings: list[str] = []
    days: list[HolidayDay] = []
    for y in years:
        try:
            data = load_holidays(y)
        except HolidayDataError as exc:
            warnings.append(str(exc))
            continue
        if data is None:
            warnings.append(f"没有 {y} 年的内置放假数据")
        else:
            days.extend(data.days)

    occurrences_by_date: dict[date, list] = {}
    for course in tt.courses:
        for occ in resolve_course(course, total_weeks=tt.weeks_total):
            if occ.week is None:
                continue
            try:
                day = calendar.date_for(occ.week, occ.day)
            except SemesterError:
                continue
            occurrences_by_date.setdefault(day, []).append(occ)

    notices: list[HolidaySpan] = []
    for span in _group_spans(days):
        start = max(span.start, term_start)
        end = min(span.end, term_end)
        if start > end:
            continue
        affected: list[str] = []
        if span.is_off:
            current = start
            while current <= end:
                for occ in sorted(
                    occurrences_by_date.get(current, []),
                    key=lambda o: (o.start, o.name),
                ):
                    affected.append(f"{current.strftime('%m-%d')} {occ.name} ({occ.slot_text()})")
                current += timedelta(days=1)
        notices.append(HolidaySpan(
            name=span.name, start=start, end=end, is_off=span.is_off,
            affected=tuple(affected),
        ))

    notices.sort(key=lambda n: (n.start, not n.is_off, n.name))
    return HolidayReport(year=fallback_year, notices=notices, warnings=warnings)
