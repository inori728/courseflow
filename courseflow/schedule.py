"""把课程展开成"某一周实际发生的课".

Timetable 保存用户写下的原始课表; Occurrence 表示展开后的单次课程.
skip / changes 以及后续的调休规则都在这一层应用, 输出模块不再自己解析周次.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .model import DAYS, Course, Timetable
from .weeks import DEFAULT_TOTAL_WEEKS, parse_weeks


@dataclass(frozen=True)
class Occurrence:
    """某一周的一次实际课程; week 为 None 表示周次无法确认."""

    week: Optional[int]
    day: int
    start: int
    end: int
    room: str
    name: str
    course: Course = field(compare=False, repr=False)

    def slot_text(self) -> str:
        span = f"{self.start}-{self.end}" if self.start != self.end else str(self.start)
        return f"{DAYS[self.day]} {span} 节"


@dataclass(frozen=True)
class ScheduleBlock:
    """同一门课在同一时段、多个周次合并后的块, 供冲突检测使用."""

    day: int
    start: int
    end: int
    weeks: Optional[frozenset[int]]
    name: str


def resolve_course(course: Course, total_weeks: int = DEFAULT_TOTAL_WEEKS) -> list[Occurrence]:
    """展开一门课, 应用停课和单次调整."""
    weeks = parse_weeks(course.weeks, total_weeks) if course.weeks else None
    result: list[Occurrence] = []

    if weeks is None:
        result.append(Occurrence(
            week=None, day=course.day, start=course.start, end=course.end,
            room=course.room, name=course.name, course=course,
        ))
    else:
        base = set(weeks)
        base -= set(course.skip or [])
        base -= {ch.week for ch in course.changes}
        for week in sorted(base):
            result.append(Occurrence(
                week=week, day=course.day, start=course.start, end=course.end,
                room=course.room, name=course.name, course=course,
            ))

    for ch in course.changes:
        day = ch.day if ch.day is not None else course.day
        start = ch.start if ch.start is not None else course.start
        end = ch.end if ch.end is not None else course.end
        result.append(Occurrence(
            week=ch.week, day=day, start=start, end=end,
            room=ch.room or course.room, name=course.name, course=course,
        ))
    return result


def resolve_timetable(tt: Timetable, total_weeks: int = DEFAULT_TOTAL_WEEKS) -> list[Occurrence]:
    """展开整张课表."""
    out: list[Occurrence] = []
    for course in tt.courses:
        out.extend(resolve_course(course, total_weeks=total_weeks))
    return out


def resolve_blocks(course: Course, total_weeks: int = DEFAULT_TOTAL_WEEKS) -> list[ScheduleBlock]:
    """把同一时段的周次合并, 保留"周次无法确认"的块."""
    grouped: dict[tuple[int, int, int], set[int]] = {}
    unknown = False
    for occ in resolve_course(course, total_weeks=total_weeks):
        key = (occ.day, occ.start, occ.end)
        if occ.week is None:
            unknown = True
        else:
            grouped.setdefault(key, set()).add(occ.week)

    blocks = [
        ScheduleBlock(day=day, start=start, end=end,
                      weeks=frozenset(weeks), name=course.name)
        for (day, start, end), weeks in sorted(grouped.items())
    ]
    if unknown:
        blocks.append(ScheduleBlock(
            day=course.day, start=course.start, end=course.end,
            weeks=None, name=course.name,
        ))
    return blocks


def period_cells(occ: Occurrence) -> list[tuple[int, int]]:
    """把一次课拆成单节格子; 组队模式和忙闲图后续使用."""
    return [(occ.day, period) for period in range(occ.start, occ.end + 1)]
