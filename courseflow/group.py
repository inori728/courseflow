"""Privacy-preserving busy cards and deterministic common availability."""
from __future__ import annotations

import base64
import binascii
import json
import zlib
from dataclasses import dataclass, field
from datetime import date, time, timedelta
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

from .ics import write_calendar
from .model import Course, DAYS, Timetable
from .render import load_font
from .schedule import resolve_timetable
from .semester import SemesterCalendar, SemesterError
from .settings import atomic_text


class GroupError(ValueError):
    pass


@dataclass
class BusyCard:
    name: str
    semester_start: date
    busy: dict[int, set[int]]
    period_times: dict[int, tuple[time, time]] = field(default_factory=dict)
    timezone: str = "Asia/Shanghai"
    campus: str = ""

    def payload(self) -> dict:
        return {
            "v": 1, "name": self.name, "start": self.semester_start.isoformat(),
            "busy": {str(w): sorted(cells) for w, cells in sorted(self.busy.items())},
            "period_times": {str(p): f"{span[0].strftime('%H:%M')}-{span[1].strftime('%H:%M')}"
                             for p, span in sorted(self.period_times.items())},
            "timezone": self.timezone, "campus": self.campus,
        }

    def encode(self) -> str:
        raw = json.dumps(self.payload(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        return f"CF1.{encoded}.{zlib.crc32(raw):08x}"


def decode_card(text: str) -> BusyCard:
    if len(text) > 250000:
        raise GroupError("忙闲卡过大.")
    parts = text.strip().split(".")
    if len(parts) != 3 or parts[0] != "CF1":
        raise GroupError("忙闲卡格式不正确, 请复制完整 CF1 短码.")
    try:
        raw = base64.b64decode(parts[1] + "=" * (-len(parts[1]) % 4), altchars=b"-_", validate=True)
        if f"{zlib.crc32(raw):08x}" != parts[2].lower():
            raise GroupError("忙闲卡校验失败, 内容可能没有复制完整.")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("v") != 1:
            raise GroupError("不支持这个忙闲卡版本.")
        name = payload["name"]
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise GroupError("忙闲卡需要有效的成员名称.")
        anchor = date.fromisoformat(payload["start"])
        if anchor.weekday() != 0:
            raise GroupError("忙闲卡的学期起始日期必须是周一.")
        rows = payload["busy"]
        if not isinstance(rows, dict) or not 1 <= len(rows) <= 104:
            raise GroupError("忙闲卡应包含 1-104 个已填写的周次.")
        busy = {}
        for week, cells in rows.items():
            number = int(week)
            if str(number) != str(week) or not 1 <= number <= 104 or not isinstance(cells, list):
                raise GroupError("忙闲卡的周次格式不正确.")
            if any(isinstance(c, bool) or not isinstance(c, int) or not 0 <= c < 84 for c in cells):
                raise GroupError("忙闲格必须在 7 天 x 12 节范围内.")
            busy[number] = set(cells)
        clocks = payload.get("period_times", {})
        if not isinstance(clocks, dict):
            raise GroupError("忙闲卡的作息信息格式不正确.")
        times = {}
        for key, value in clocks.items():
            period = int(key)
            a, b = str(value).split("-")
            start, end = time.fromisoformat(a), time.fromisoformat(b)
            if not 1 <= period <= 12 or end <= start:
                raise GroupError("忙闲卡的节次时间不正确.")
            times[period] = (start, end)
        timezone = str(payload.get("timezone", "Asia/Shanghai"))[:80]
        return BusyCard(name.strip(), anchor, busy, times, timezone, str(payload.get("campus", ""))[:80])
    except (ValueError, KeyError, TypeError, binascii.Error) as exc:
        if isinstance(exc, GroupError):
            raise
        raise GroupError("忙闲卡内容无法解析, 请重新导出.") from exc


def card_from_timetable(tt: Timetable, name: str, weeks=None, campus: str = "") -> BusyCard:
    try:
        calendar = SemesterCalendar.from_timetable(tt)
    except SemesterError as exc:
        raise GroupError(str(exc)) from exc
    if not name.strip():
        raise GroupError("请填写成员名称.")
    if not 1 <= tt.weeks_total <= 104:
        raise GroupError("组队支持 1-104 周的学期.")
    selected = sorted(set(weeks if weeks is not None else range(1, tt.weeks_total + 1)))
    if not selected or any(isinstance(w, bool) or not isinstance(w, int) or not 1 <= w <= tt.weeks_total for w in selected):
        raise GroupError("请选择学期范围内的周次.")
    busy = {week: set() for week in selected}
    for occ in resolve_timetable(tt, tt.weeks_total):
        if occ.week is None:
            raise GroupError(f"'{occ.name}' 的周次无法确认, 请先校对, 不能将未知课程当成空闲.")
        if not 1 <= occ.week <= tt.weeks_total:
            raise GroupError(f"'{occ.name}' 的周次超出学期范围, 请先校对.")
        if occ.week in busy:
            busy[occ.week].update(occ.day * 12 + period - 1 for period in range(occ.start, occ.end + 1))
    return BusyCard(name.strip()[:80], calendar.start, busy, dict(tt.period_times), tt.timezone, campus.strip()[:80])


@dataclass(frozen=True)
class FreeWindow:
    day: int
    start: int
    end: int

    def describe(self) -> str:
        return f"{DAYS[self.day]} {self.start}-{self.end} 节"


@dataclass
class GroupResult:
    week: int
    monday: date
    names: list[str]
    counts: list[int]
    windows: list[FreeWindow]
    period_times: dict[int, tuple[time, time]]
    timezone: str
    warnings: list[str] = field(default_factory=list)
    campus_hint: str = ""

    def describe(self) -> str:
        lines = [f"第 {self.week} 周 ({self.monday.isoformat()} 起)", f"成员: {', '.join(self.names)}"]
        lines.extend("提示: " + warning for warning in self.warnings)
        if self.campus_hint:
            lines.append(self.campus_hint)
        lines.append("全员空闲时段:" if self.windows else "没有满足条件的全员空闲时段.")
        lines.extend("- " + window.describe() for window in self.windows)
        lines.append("结果只覆盖成员提供的忙闲信息, 约定会议前请确认课外安排.")
        return "\n".join(lines)


def common_free(cards: list[BusyCard], week: int, minimum_periods: int = 2,
                start_period: int = 1, end_period: int = 12) -> GroupResult:
    if not 1 <= len(cards) <= 100:
        raise GroupError("请添加 1-100 位成员.")
    if not 1 <= minimum_periods <= 12 or not 1 <= start_period <= end_period <= 12:
        raise GroupError("空闲时长或节次范围不正确.")
    if not 1 <= week <= 104:
        raise GroupError("周次超出范围.")
    names = [card.name for card in cards]
    if len(set(names)) != len(names):
        raise GroupError("成员名称重复, 请修改名称后再求交.")
    monday = cards[0].semester_start + timedelta(weeks=week - 1)
    counts = [0] * 84
    clocks = next((card.period_times for card in cards if card.period_times), {})
    timezone = cards[0].timezone
    warnings = []
    for card in cards:
        if card.timezone != timezone:
            raise GroupError("成员时区不一致, 请统一后再求交.")
        if card.period_times and clocks and card.period_times != clocks:
            raise GroupError("成员的节次作息不同, 不能直接按节次求交, 请先统一作息.")
        if not card.period_times:
            warnings.append(f"{card.name} 未提供作息时间, 请确认其节次与其他成员一致.")
        delta = (monday - card.semester_start).days
        if delta % 7:
            raise GroupError("成员的学期起始星期不一致.")
        own_week = delta // 7 + 1
        if own_week not in card.busy:
            raise GroupError(f"{card.name} 没有提供 {monday.isoformat()} 这一周的忙闲数据, 不能按全空闲处理.")
        for cell in card.busy[own_week]:
            counts[cell] += 1
    windows = []
    for day in range(7):
        start = None
        for period in range(start_period, end_period + 2):
            free = period <= end_period and counts[day * 12 + period - 1] == 0
            if free and start is None:
                start = period
            if not free and start is not None:
                if period - start >= minimum_periods:
                    windows.append(FreeWindow(day, start, period - 1))
                start = None
    campuses = {card.campus for card in cards}
    hint = f"成员填写的校区均为: {next(iter(campuses))}" if len(campuses) == 1 and "" not in campuses else ""
    return GroupResult(week, monday, names, counts, windows, dict(clocks), timezone, warnings, hint)


def render_heatmap(result: GroupResult, out) -> Path:
    image = Image.new("RGB", (1320, 1150), "#f3f6fb")
    draw = ImageDraw.Draw(image)
    title, label, small = load_font(37, True), load_font(23), load_font(19)
    draw.text((75, 48), "CourseFlow / 组队忙闲", font=title, fill="#17233d")
    draw.text((75, 105), f"{result.monday.isoformat()} 起 / {len(result.names)} 位成员 / 绿色表示全员空闲", font=label, fill="#59677e")
    x, y, width, height = 130, 225, 157, 60
    for day in range(7):
        draw.text((x + day * width + 37, y - 48), DAYS[day], font=label, fill="#17233d")
    for period in range(1, 13):
        draw.text((57, y + (period - 1) * height + 13), str(period), font=label, fill="#59677e")
        for day in range(7):
            count = result.counts[day * 12 + period - 1]
            color = "#d9f3e7" if count == 0 else ("#d9e2f7" if count < len(result.names) else "#9aaed8")
            left, top = x + day * width, y + (period - 1) * height
            draw.rounded_rectangle((left, top, left + width - 8, top + height - 7), radius=9, fill=color)
            draw.text((left + 20, top + 13), "全空闲" if count == 0 else f"{count} 人忙", font=small, fill="#27413c" if not count else "#334c77")
    draw.text((75, 990), "仅依据成员提供的忙闲信息, 会议前请确认课外安排.", font=small, fill="#59677e")
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    return path


def export_meeting(result: GroupResult, window: FreeWindow, title: str, out,
                   start: Optional[int] = None, end: Optional[int] = None) -> Path:
    first = window.start if start is None else start
    last = window.end if end is None else end
    if window not in result.windows or not window.start <= first <= last <= window.end:
        raise GroupError("会议时间应位于所选的全员空闲时段内.")
    if not title.strip():
        raise GroupError("请填写会议名称.")
    tt = Timetable(
        term=title.strip(), semester_start=result.monday, weeks_total=1,
        period_times=result.period_times, timezone=result.timezone,
        courses=[Course(name=title.strip(), day=window.day, start=first, end=last, weeks="1周")],
    )
    return write_calendar(tt, out)


def save_card(card: BusyCard, out) -> Path:
    path = Path(out)
    atomic_text(path, card.encode() + "\n")
    return path
