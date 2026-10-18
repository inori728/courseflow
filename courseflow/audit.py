"""课表校对:时间冲突,缺失信息,改动明细--全部本地,确定性计算,没有 AI.

这个模块回答三个问题:
- 哪两条课会"撞车"(同一天,节次重叠,周次也重叠)?
- 哪些条目信息不全(缺教室 / 缺周次 / 周次无法识别 / 调整越界)?
- 手动改过哪些地方(停课 / 调课 / 换教室的明细)?
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .model import DAYS, Course, Timetable, parse_weekset


def _fmt_weeks(weeks) -> str:
    """把周次集合压成好读的文字:8-12 / 3,5,7 这类."""
    ws = sorted(weeks)
    if not ws:
        return ""
    runs: list[tuple[int, int]] = []
    start = prev = ws[0]
    for w in ws[1:]:
        if w == prev + 1:
            prev = w
            continue
        runs.append((start, prev))
        start = prev = w
    runs.append((start, prev))
    parts = []
    for a, b in runs:
        if a == b:
            parts.append(str(a))
        elif b == a + 1:
            parts.append(f"{a},{b}")
        else:
            parts.append(f"{a}-{b}")
    return ",".join(parts)


def _slot_text(day: int, start: int, end: int) -> str:
    span = f"{start}-{end}" if start != end else str(start)
    return f"{DAYS[day]} {span} 节"


def _occurrences(c: Course) -> list[tuple[int, int, int, Optional[set[int]]]]:
    """把一条课拆成若干 (day, start, end, 周次集合或 None) 时段(处理停课 / 调整)."""
    occ: list[tuple[int, int, int, Optional[set[int]]]] = []
    weeks = parse_weekset(c.weeks) if c.weeks else None
    if weeks is None:
        occ.append((c.day, c.start, c.end, None))
    else:
        base = set(weeks)
        base -= set(c.skip or [])
        base -= {ch.week for ch in c.changes}
        if base:
            occ.append((c.day, c.start, c.end, base))
    for ch in c.changes:
        day = ch.day if ch.day is not None else c.day
        st = ch.start if ch.start is not None else c.start
        en = ch.end if ch.end is not None else c.end
        occ.append((day, st, en, {ch.week}))
    return occ


def find_conflicts(tt: Timetable) -> list[str]:
    """找出时间冲突(同一天 + 节次重叠 + 周次也重叠);返回给人看的文字列表."""
    items = [(c, _occurrences(c)) for c in tt.courses]
    out: list[str] = []
    for i in range(len(items)):
        a, oa = items[i]
        for j in range(i + 1, len(items)):
            b, ob = items[j]
            for day1, s1, e1, w1 in oa:
                for day2, s2, e2, w2 in ob:
                    if day1 != day2 or s1 > e2 or s2 > e1:
                        continue
                    if w1 is None or w2 is None:
                        weeks_txt = "周次无法确认"
                    else:
                        inter = w1 & w2
                        if not inter:
                            continue
                        weeks_txt = f"第 {_fmt_weeks(inter)} 周"
                    ov_s, ov_e = max(s1, s2), min(e1, e2)
                    text = f"'{a.name}' × '{b.name}' {_slot_text(day1, ov_s, ov_e)}重叠({weeks_txt})"
                    if text not in out:
                        out.append(text)
    return out


def data_issues(tt: Timetable) -> list[str]:
    """列出信息不全 / 需要人工确认的条目."""
    out: list[str] = []
    for c in tt.courses:
        label = f"'{c.name}'({_slot_text(c.day, c.start, c.end)})"
        if not c.room:
            out.append(f"{label} 缺教室")
        if not c.weeks:
            out.append(f"{label} 缺周次")
            continue
        ws = parse_weekset(c.weeks)
        if ws is None:
            out.append(f"{label} 周次无法识别:'{c.weeks}'(冲突检测会按'周次无法确认'提示)")
            continue
        for w in c.skip or []:
            if w not in ws:
                out.append(f"{label} 停课周次 {w} 不在课程周次内")
        for ch in c.changes:
            if ch.week not in ws:
                out.append(f"{label} 调整周次 {ch.week} 不在课程周次内")
    return out


def changed_list(tt: Timetable) -> list[str]:
    """手动改动的明细(停课 / 调整),给用户核对用."""
    out: list[str] = []
    for c in tt.courses:
        for w in c.skip or []:
            out.append(f"'{c.name}' 第 {w} 周停课")
        for ch in c.changes:
            out.append(f"'{c.name}' {ch.describe()}")
    return out


@dataclass
class Review:
    conflicts: list[str]
    issues: list[str]
    changes: list[str]

    @property
    def problem_count(self) -> int:
        return len(self.conflicts) + len(self.issues)


def review(tt: Timetable) -> Review:
    """一次性算好校对的三块内容."""
    return Review(
        conflicts=find_conflicts(tt),
        issues=data_issues(tt),
        changes=changed_list(tt),
    )
