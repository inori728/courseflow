"""课表数据模型 + '课表源文件'的读写.

课表源文件(一个文本文件)是整个项目的中间层:
一切导入最终都变成它,一切输出(壁纸 / 日历 / 挂图)都从它出发.
它的好处是纯文本--用记事本就能改,改了也方便看出"这行是谁动的".
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

# 周一 ~ 周日,代码里用 0~6 表示
DAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

_DAY_ALIASES: dict[str, int] = {}
for _i, _d in enumerate(DAYS):
    _DAY_ALIASES[_d] = _i                              # 周一
    _DAY_ALIASES[_d.replace("周", "星期")] = _i        # 星期一
    _DAY_ALIASES[_d.replace("周", "礼拜")] = _i        # 礼拜一
    _DAY_ALIASES[str(_i + 1)] = _i                     # "1" ~ "7"


def parse_day(value) -> Optional[int]:
    """把 周一 / 星期一 / 1 等写法解析成 0~6;无法识别时返回 None."""
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
    """把 1-2 / 第1-2节 / 3,4 等写法解析成(开始节, 结束节);无法识别时返回 None."""
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


SEMESTER_DEFAULT_WEEKS = 16   # 单周 / 双周这类没写范围时,按 1~16 周计

_WEEK_RANGE_RE = re.compile(r"(\d+)\s*[-\u2013\u2014~至]\s*(\d+)")
_WEEK_NUM_RE = re.compile(r"\d+")


def parse_weekset(text) -> Optional[set[int]]:
    """把周次文字解析成周次集合(如 "1-16周" / "第2周" / "1-16周单周");无法识别时返回 None."""
    s = str(text or "").strip()
    if not s:
        return None
    weeks: set[int] = set()
    for a, b in _WEEK_RANGE_RE.findall(s):
        a, b = int(a), int(b)
        weeks.update(range(min(a, b), max(a, b) + 1))
    # 区间之间还可能夹着单独的周次(如 "1-4,6,8-10周" 里的 6),一并算上
    weeks.update(int(n) for n in _WEEK_NUM_RE.findall(s))
    if not weeks:
        if not any(k in s for k in ("单周", "双周", "每周", "全周", "周")):
            return None
        weeks = set(range(1, SEMESTER_DEFAULT_WEEKS + 1))
    if "单周" in s:
        weeks = {w for w in weeks if w % 2 == 1}
    elif "双周" in s:
        weeks = {w for w in weeks if w % 2 == 0}
    return weeks or None


@dataclass
class Change:
    """单次调整:把某一周的一次课改到别的日子 / 节次 / 教室(手改源文件用)."""

    week: int
    day: Optional[int] = None
    start: Optional[int] = None
    end: Optional[int] = None
    room: str = ""

    def describe(self) -> str:
        parts = []
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


def _parse_skip(value, warn) -> list[int]:
    """解析 skip 字段(停课周次).支持 [8, 9] / "8,9" / "8-9周" 等写法."""
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        if not value:
            return []
        value = ",".join(str(v) for v in value)
    weeks = parse_weekset(str(value))
    if weeks is None:
        warn(f"skip 无法识别,已忽略:{value!r}")
        return []
    return sorted(weeks)


def _parse_changes(value, warn) -> list[Change]:
    """解析 changes 字段(单次调整列表);有问题的条目跳过并记 warning."""
    out: list[Change] = []
    if value is None:
        return out
    if not isinstance(value, list):
        warn(f"changes 应该是一个列表,已忽略:{value!r}")
        return out
    for i, item in enumerate(value, 1):
        if not isinstance(item, dict):
            warn(f"changes 第 {i} 条不是字典,已跳过")
            continue
        wk = parse_weekset(item.get("week"))
        if wk is None or len(wk) != 1:
            warn(f"changes 第 {i} 条的 week 应为单周次(如 10),已跳过")
            continue
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
        if day is None and periods is None and not room:
            warn(f"changes 第 {i} 条没写明改什么(day / periods / room 至少一个),已跳过")
            continue
        out.append(Change(
            week=min(wk), day=day,
            start=periods[0] if periods else None,
            end=periods[1] if periods else None,
            room=room,
        ))
    return out


@dataclass
class Course:
    """一门课在课表里的"一条"安排(同一天多门就写多条)."""

    name: str
    day: int            # 0=周一 ... 6=周日
    start: int          # 开始节次(1~12)
    end: int            # 结束节次
    room: str = ""      # 教室
    weeks: str = ""     # 周次原文,如 "1-16周"(先原样保存,规则引擎在后面的迭代做)
    skip: list[int] = field(default_factory=list)       # 停课周次(第几周不上)
    changes: list[Change] = field(default_factory=list) # 单次调整(某周改到别的时间 / 教室)

    @property
    def day_name(self) -> str:
        return DAYS[self.day]

    def slot_text(self) -> str:
        span = f"{self.start}-{self.end}" if self.start != self.end else str(self.start)
        return f"{self.day_name} {span}节"


@dataclass
class Timetable:
    """一张完整课表:学期名 + 若干条课程安排."""

    term: str = ""
    courses: list[Course] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list, compare=False, repr=False)

    def sorted_courses(self) -> list[Course]:
        return sorted(self.courses, key=lambda c: (c.day, c.start, c.name))

    def __len__(self) -> int:
        return len(self.courses)


class SourceFileError(ValueError):
    """课表源文件读不动时抛的错(错误文案会直接给用户看)."""


# 生成源文件时带的说明行(用记事本打开能看到)
SOURCE_HEADER = (
    "# CourseFlow 课表源文件 -- 用记事本就能改;改完可跑  term check  校对,再跑  term wallpaper  重新出图\n"
)


def load_source(path) -> Timetable:
    """读取课表源文件.遇到读不动的条目会收集到 warnings,不打断整体."""
    p = Path(path)
    if not p.exists():
        raise SourceFileError(f"没找到课表源文件:{p}")

    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SourceFileError(f"课表源文件的格式有问题(YAML 解析失败):{p}\n  {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise SourceFileError("课表源文件的最外层应该是一个字典(term / courses 两节)")

    tt = Timetable(term=str(data.get("term") or "").strip())
    for i, item in enumerate(data.get("courses") or [], 1):
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
        skip = _parse_skip(item.get("skip"), lambda msg: tt.warnings.append(prefix + msg))
        changes = _parse_changes(item.get("changes"), lambda msg: tt.warnings.append(prefix + msg))
        tt.courses.append(
            Course(
                name=name, day=day, start=start, end=end,
                room=str(item.get("room") or "").strip(),
                weeks=str(item.get("weeks") or "").strip(),
                skip=skip,
                changes=changes,
            )
        )
    return tt


def save_source(tt: Timetable, path) -> None:
    """把课表写回源文件(带一行使用说明;中文不转义)."""
    courses = []
    for c in tt.sorted_courses():
        item: dict = {
            "name": c.name,
            "day": c.day_name,
            "periods": f"{c.start}-{c.end}" if c.start != c.end else str(c.start),
            "weeks": c.weeks,
            "room": c.room,
        }
        if c.skip:
            item["skip"] = list(c.skip)
        if c.changes:
            item["changes"] = [_change_to_dict(ch) for ch in c.changes]
        courses.append(item)
    data = {"term": tt.term, "courses": courses}
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    Path(path).write_text(SOURCE_HEADER + text, encoding="utf-8")


def _change_to_dict(ch: Change) -> dict:
    """把一条单次调整写回源文件的字典形式(只写实际填了的字段)."""
    item: dict = {"week": ch.week}
    if ch.day is not None:
        item["day"] = DAYS[ch.day]
    if ch.start is not None:
        item["periods"] = f"{ch.start}-{ch.end}" if ch.start != ch.end else str(ch.start)
    if ch.room:
        item["room"] = ch.room
    return item
