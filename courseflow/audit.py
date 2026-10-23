"""课表校对: 时间冲突, 缺失信息, 改动明细--全部本地, 确定性计算, 没有 AI.

周次展开和 skip / changes 的处理统一交给 schedule.py; 这里只负责解释结果.
"""
from __future__ import annotations

from dataclasses import dataclass

from .model import DAYS, Timetable
from .schedule import resolve_blocks
from .weeks import parse_weeks


def _fmt_weeks(weeks) -> str:
    """把周次集合压成好读的文字: 8-12 / 3,5,7 这类."""
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
        else:
            parts.append(f"{a}-{b}")
    return ",".join(parts)


def _slot_text(day: int, start: int, end: int) -> str:
    span = f"{start}-{end}" if start != end else str(start)
    return f"{DAYS[day]} {span} 节"


def find_conflicts(tt: Timetable) -> list[str]:
    """找出时间冲突(同一天 + 节次重叠 + 周次也重叠); 返回给人看的文字列表."""
    items = [(c, resolve_blocks(c, total_weeks=tt.weeks_total)) for c in tt.courses]
    out: list[str] = []
    for i in range(len(items)):
        a, blocks_a = items[i]
        for j in range(i + 1, len(items)):
            b, blocks_b = items[j]
            for block_a in blocks_a:
                for block_b in blocks_b:
                    if block_a.day != block_b.day:
                        continue
                    if block_a.start > block_b.end or block_b.start > block_a.end:
                        continue
                    if block_a.weeks is None or block_b.weeks is None:
                        weeks_txt = "周次无法确认"
                    else:
                        inter = block_a.weeks & block_b.weeks
                        if not inter:
                            continue
                        weeks_txt = f"第 {_fmt_weeks(inter)} 周"
                    ov_s = max(block_a.start, block_b.start)
                    ov_e = min(block_a.end, block_b.end)
                    text = (
                        f"'{a.name}' × '{b.name}' "
                        f"{_slot_text(block_a.day, ov_s, ov_e)}重叠({weeks_txt})"
                    )
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
        ws = parse_weeks(c.weeks, total_weeks=tt.weeks_total)
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
    """手动改动的明细(停课 / 调整), 给用户核对用."""
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
