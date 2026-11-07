"""课表数据模型.

Timetable / Course 保存用户写下的原始课表; 周次展开和 skip / changes 的应用
在 schedule.py. 源文件读写和字段校验在 source.py.
"""
from __future__ import annotations

import re
import hashlib
import json
from dataclasses import asdict
from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional

from .weeks import DEFAULT_TOTAL_WEEKS

# 周一 ~ 周日, 代码里用 0~6 表示
DAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

_DAY_ALIASES: dict[str, int] = {}
for _i, _d in enumerate(DAYS):
    _DAY_ALIASES[_d] = _i                              # 周一
    _DAY_ALIASES[_d.replace("周", "星期")] = _i        # 星期一
    _DAY_ALIASES[_d.replace("周", "礼拜")] = _i        # 礼拜一
    _DAY_ALIASES[str(_i + 1)] = _i                     # "1" ~ "7"


def parse_day(value) -> Optional[int]:
    """把 周一 / 星期一 / 1 等写法解析成 0~6; 无法识别时返回 None."""
    s = str(value).strip()
    for key, idx in _DAY_ALIASES.items():
        if s == key:
            return idx
    # 长一点的文字里夹着星期名也算(如 "周一(单周)")
    for key, idx in _DAY_ALIASES.items():
        if not key.isdigit() and key in s:
            return idx
    return None


def parse_periods(value) -> Optional[tuple[int, int]]:
    """把 1-2 / 第1-2节 / 3,4 等写法解析成(开始节, 结束节); 无法识别时返回 None."""
    s = str(value).strip()
    rng = re.search(r"(\d+)\s*[-\u2013\u2014~至,]\s*(\d+)", s)
    if rng:
        a, b = int(rng.group(1)), int(rng.group(2))
        return (min(a, b), max(a, b))
    one = re.search(r"\d+", s)
    if one:
        n = int(one.group())
        return (n, n)
    return None


@dataclass
class Change:
    """单次调整: 把某一周的一次课改到别的日子 / 节次 / 教室(手改源文件用)."""

    week: int
    day: Optional[int] = None
    start: Optional[int] = None
    end: Optional[int] = None
    room: str = ""
    extra: dict = field(default_factory=dict, compare=False, repr=False)
    target_week: Optional[int] = None

    def describe(self) -> str:
        parts = []
        if self.target_week is not None and self.target_week != self.week:
            parts.append(f"第 {self.target_week} 周")
        if self.day is not None:
            parts.append(DAYS[self.day])
        if self.start is not None:
            span = f"{self.start}-{self.end}" if self.start != self.end else str(self.start)
            parts.append(f"{span} 节")
        if self.room:
            parts.append(f"@{self.room}")
        if not parts:
            return f"第 {self.week} 周(没写明改什么)"
        return f"第 {self.week} 周 → {' '.join(parts)}"


@dataclass
class Course:
    """一门课在课表里的一条安排(同一天多门就写多条)."""

    name: str
    day: int            # 0=周一 ... 6=周日
    start: int          # 开始节次(1~12)
    end: int            # 结束节次
    room: str = ""      # 教室
    weeks: str = ""     # 周次原文, 如 "1-16周"; 解析在 weeks.py
    skip: list[int] = field(default_factory=list)       # 停课周次
    changes: list[Change] = field(default_factory=list) # 单次调整
    extra: dict = field(default_factory=dict, compare=False, repr=False)

    @property
    def day_name(self) -> str:
        return DAYS[self.day]

    def slot_text(self) -> str:
        span = f"{self.start}-{self.end}" if self.start != self.end else str(self.start)
        return f"{self.day_name} {span} 节"


@dataclass
class Timetable:
    """一张完整课表: 学期信息 + 若干条课程安排."""

    term: str = ""
    semester_start: Optional[date] = None
    weeks_total: int = DEFAULT_TOTAL_WEEKS
    period_times: dict[int, tuple[time, time]] = field(default_factory=dict)
    timezone: str = "Asia/Shanghai"
    schema_version: int = 2
    courses: list[Course] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list, compare=False, repr=False)
    extra: dict = field(default_factory=dict, compare=False, repr=False)

    def sorted_courses(self) -> list[Course]:
        return sorted(self.courses, key=lambda c: (c.day, c.start, c.name))

    def __len__(self) -> int:
        return len(self.courses)


def timetable_signature(tt: Timetable) -> str:
    content = json.dumps(asdict(tt), default=str, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
