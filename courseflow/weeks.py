"""周次表达式的统一解析.

这里是项目里唯一负责"周次文字 -> 周次集合"的模块. 导入层用它切分格子,
源文件用它校验 skip / changes, 校对, 日历和组队也都从这里取结果.
"""
from __future__ import annotations

import re
from typing import Optional

DEFAULT_TOTAL_WEEKS = 16

_CN_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}

# 阿拉伯数字或中文数字. 中文数字先覆盖 1~99 的常见写法.
_NUM = r"(?:\d+|[零〇一二两三四五六七八九十]+)"
_ITEM = rf"(?:第\s*)?{_NUM}(?:\s*[-\u2013\u2014~至]\s*{_NUM})?"
_ITEM_WEEK = rf"{_ITEM}\s*周?"
_LIST = rf"{_ITEM_WEEK}(?:\s*[,\uff0c\u3001]\s*{_ITEM_WEEK})*"
_MOD = r"(?:\s*(?:[\uff08(]\s*[单双]{1,2}(?:周)?\s*[\uff09)]|单周|双周))?"

# 用于在整段格子文字里找出"像周次"的片段. 是否真的能解析由 parse_weeks 判断.
WEEK_EXPR_RE = re.compile(rf"(?:{_LIST}{_MOD}|单周|双周|每周|全周)")

_RANGE_RE = re.compile(rf"({_NUM})\s*[-\u2013\u2014~至]\s*({_NUM})")
_NUM_RE = re.compile(_NUM)
_SINGLE_MOD_RE = re.compile(r"(?:单周|[\uff08(]\s*单(?:周)?\s*[\uff09)])")
_DOUBLE_MOD_RE = re.compile(r"(?:双周|[\uff08(]\s*双(?:周)?\s*[\uff09)])")


def _cn_to_int(text: str) -> Optional[int]:
    """把单个中文数字片段转成整数; 支持 3 / 十六 / 二十 / 二十三."""
    s = text.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if "十" in s:
        left, right = s.split("十", 1)
        if left:
            tens = _CN_DIGITS.get(left[-1])
        else:
            tens = 1
        if right:
            ones = _CN_DIGITS.get(right[0])
        else:
            ones = 0
        if tens is None or ones is None:
            return None
        return tens * 10 + ones
    if len(s) == 1:
        return _CN_DIGITS.get(s)
    values = [_CN_DIGITS.get(ch) for ch in s]
    if any(v is None for v in values):
        return None
    return int("".join(str(v) for v in values))


def _number(text: str) -> Optional[int]:
    n = _cn_to_int(text)
    if n is None or n < 1:
        return None
    return n


def parse_weeks(text, total_weeks: int = DEFAULT_TOTAL_WEEKS) -> Optional[set[int]]:
    """解析周次文字, 返回周次集合; 无法确认时返回 None.

    支持:
    - 1-16周 / 第2周 / 第三周 / 三至十六周
    - 1-4,6,8-10周 / 第1-4周,第6周
    - 单周 / 双周 / 每周 / 全周
    - 1-16周(单) / 1-16周(双周) / 1-16周 单周
    """
    s = str(text or "").strip()
    if not s:
        return None

    try:
        total = max(int(total_weeks), 1)
    except (TypeError, ValueError):
        total = DEFAULT_TOTAL_WEEKS

    weeks: set[int] = set()
    for m in _RANGE_RE.finditer(s):
        a, b = _number(m.group(1)), _number(m.group(2))
        if a is None or b is None:
            continue
        weeks.update(range(min(a, b), max(a, b) + 1))

    # 区间之间还可能夹着单独的周次, 如 1-4,6,8-10周 里的 6.
    for m in _NUM_RE.finditer(s):
        n = _number(m.group())
        if n is not None:
            weeks.add(n)

    if not weeks:
        if "每周" in s or "全周" in s:
            weeks = set(range(1, total + 1))
        elif "单周" in s:
            weeks = set(range(1, total + 1, 2))
        elif "双周" in s:
            weeks = set(range(2, total + 1, 2))
        else:
            # 只写了"周"但没有可确认的数字或单双周语义, 不再静默按整学期.
            return None

    if "单双" in s:
        return None

    single = bool(_SINGLE_MOD_RE.search(s))
    double = bool(_DOUBLE_MOD_RE.search(s))
    if single and double:
        return None
    if single:
        weeks = {w for w in weeks if w % 2 == 1}
    elif double:
        weeks = {w for w in weeks if w % 2 == 0}

    weeks = {w for w in weeks if w > 0}
    return weeks or None


def looks_like_week_expression(text) -> bool:
    """判断一段文字是否"像周次"(即使语义上暂时无法解析).

    导入切分时用它避免把 1-16周(单) 里的"(单)"误当成新课程;
    是否真的可解析仍由 parse_weeks 决定.
    """
    s = str(text or "").strip()
    if not s:
        return False
    if not WEEK_EXPR_RE.fullmatch(s):
        return False
    return "周" in s or s in {"单周", "双周", "每周", "全周"}
