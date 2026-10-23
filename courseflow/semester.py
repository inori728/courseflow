"""学期日期与节次时间的换算.

.ics 导出和后续组队需要把"第 N 周 + 星期几 + 第几节"变成真实日期时间.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from .model import Timetable


class SemesterError(ValueError):
    """学期时间信息不完整或无法换算时抛的错."""


def _fixed_china_tz() -> timezone:
    return timezone(timedelta(hours=8))


def _tzinfo(name: str):
    """返回时区对象. 中国时区固定 +08:00, 避免依赖 Windows 的 tzdata."""
    cleaned = (name or "").strip()
    if cleaned in {"", "Asia/Shanghai", "UTC+8", "+08:00", "Etc/GMT-8"}:
        return _fixed_china_tz(), "Asia/Shanghai"
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(cleaned), cleaned
    except Exception as exc:
        raise SemesterError(
            f"无法识别时区:{cleaned!r}. 目前默认使用 Asia/Shanghai(+08:00)."
        ) from exc


@dataclass(frozen=True)
class SemesterCalendar:
    start: date
    weeks_total: int
    period_times: dict[int, tuple[time, time]]
    tzid: str = "Asia/Shanghai"

    @classmethod
    def from_timetable(cls, tt: Timetable) -> "SemesterCalendar":
        if tt.semester_start is None:
            raise SemesterError(
                "课表缺少 semester_start(学期第一周的周一). "
                "请先在课表源文件里补上, 例如: semester_start: 2026-09-07"
            )
        if tt.semester_start.weekday() != 0:
            raise SemesterError(
                f"semester_start 必须是第 1 周的周一, 当前是 {tt.semester_start.isoformat()}"
            )
        if tt.weeks_total < 1:
            raise SemesterError("weeks_total 必须大于 0")
        tzinfo, tzid = _tzinfo(tt.timezone)
        # tzinfo is validated here; the fixed +08:00 object is rebuilt per conversion.
        del tzinfo
        return cls(
            start=tt.semester_start,
            weeks_total=tt.weeks_total,
            period_times=dict(tt.period_times),
            tzid=tzid,
        )

    def date_for(self, week: int, day: int) -> date:
        if week < 1 or week > self.weeks_total:
            raise SemesterError(f"第 {week} 周超出学期范围(1-{self.weeks_total}周)")
        if day < 0 or day > 6:
            raise SemesterError(f"星期索引超出范围:{day}")
        return self.start + timedelta(weeks=week - 1, days=day)

    def times_for(self, start_period: int, end_period: int) -> tuple[time, time]:
        if start_period not in self.period_times:
            raise SemesterError(f"period_times 缺少第 {start_period} 节的起止时间")
        if end_period not in self.period_times:
            raise SemesterError(f"period_times 缺少第 {end_period} 节的起止时间")
        start = self.period_times[start_period][0]
        end = self.period_times[end_period][1]
        if end <= start:
            raise SemesterError(
                f"第 {start_period}-{end_period} 节的结束时间早于开始时间"
            )
        return start, end

    def datetime_for(self, week: int, day: int, start_period: int,
                     end_period: Optional[int] = None) -> tuple[datetime, datetime]:
        target = self.date_for(week, day)
        start_time, end_time = self.times_for(
            start_period,
            end_period if end_period is not None else start_period,
        )
        tzinfo, _ = _tzinfo(self.tzid)
        return (
            datetime.combine(target, start_time, tzinfo),
            datetime.combine(target, end_time, tzinfo),
        )
