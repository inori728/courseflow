"""应用用例层: 给 CLI(以及后续 GUI)提供不依赖界面的操作.

CLI 只负责参数和文字输出; 真正读写课表, 校对, 出图的流程放在这里.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import copy
from typing import Optional

from .audit import Review, review
from .ics import write_calendar
from .model import Course, Timetable, timetable_signature
from .parsing import parse_pasted_text, parse_table_file, read_clipboard_text
from .render import default_wallpaper_dir, render_to_files
from .rules import HolidayReport, holiday_report
from .source import load_source, save_source


def load_timetable(path) -> Timetable:
    return load_source(path)


def default_gui_source():
    from .settings import recent_source, settings_dir
    remembered = recent_source()
    if remembered is not None:
        return remembered
    stored = settings_dir() / "课表.yaml"
    legacy = Path.cwd() / "课表.yaml"
    return stored if stored.exists() or not legacy.exists() else legacy


def remember_current_source(path):
    from .settings import remember_source
    try:
        remember_source(path)
        return True
    except OSError:
        return False


def week_calendar_data(tt, week):
    from .schedule import resolve_timetable
    from .semester import SemesterCalendar
    if isinstance(week, bool) or not isinstance(week, int) or not 1 <= week <= tt.weeks_total:
        raise ValueError("周次超出学期范围.")
    occurrences = resolve_timetable(tt, tt.weeks_total)
    dates, date_note = [], ""
    try:
        calendar = SemesterCalendar.from_timetable(tt)
        dates = [calendar.date_for(week, day) for day in range(7)]
    except ValueError:
        date_note = "请在学期与作息中核对第 1 周周一的日期."
    return {
        "week": week, "dates": dates, "date_note": date_note,
        "courses": [item for item in occurrences if item.week == week],
        "unknown": list(dict.fromkeys(item.name for item in occurrences if item.week is None)),
    }


def import_table(path, adapter=None) -> tuple[list[Course], list[str]]:
    notes: list[str] = []
    courses = parse_table_file(path, notes, adapter=adapter)
    return courses, notes


def import_clipboard() -> tuple[list[Course], list[str]]:
    notes: list[str] = []
    courses = parse_pasted_text(read_clipboard_text(), notes)
    return courses, notes


def _course_key(course: Course) -> tuple:
    return (course.name, course.day, course.start, course.end)


def prepare_import(courses: list[Course], target) -> Timetable:
    """准备导入结果: 沿用旧文件的学期信息, 并保留同键课程的手工标注."""
    target = Path(target)
    if not target.exists():
        return merge_import(courses)

    try:
        old = load_source(target)
    except Exception:
        return merge_import(courses)

    return merge_import(courses, old)


def merge_import(courses, old=None):
    tt = Timetable(courses=courses)
    if old is None:
        return tt

    tt.term = old.term
    tt.semester_start = old.semester_start
    tt.weeks_total = old.weeks_total
    tt.period_times = dict(old.period_times)
    tt.timezone = old.timezone
    tt.schema_version = old.schema_version
    tt.extra = dict(old.extra)

    old_by_key = {_course_key(c): c for c in old.courses}
    used: set[tuple] = set()
    for course in tt.courses:
        key = _course_key(course)
        previous = old_by_key.get(key)
        if previous is None or key in used:
            continue
        course.skip = list(previous.skip)
        course.changes = list(previous.changes)
        course.extra = dict(previous.extra)
        used.add(key)

    for previous in old.courses:
        if not (previous.skip or previous.changes):
            continue
        if _course_key(previous) not in used:
            tt.warnings.append(
                f"导入后未找到 '{previous.name}' 的同一时段, "
                "原停课/调课标注未保留"
            )
    return tt


def save_timetable(tt: Timetable, target, expected_signature=None) -> Optional[Path]:
    """写回课表; 旧文件存在时先备份为 .bak, 返回备份路径."""
    target = Path(target)
    if expected_signature is not None and file_signature(target) != expected_signature:
        raise ValueError("课表文件已被其他程序修改, 请重新打开后再保存, 避免覆盖.")
    backup = None
    if target.exists():
        backup = target.with_name(target.name + ".bak")
        backup.write_bytes(target.read_bytes())
    save_source(tt, target)
    return backup


def prepare_demo_source(target, sample_path, force: bool = False) -> bool:
    """准备示例课表; 返回是否真的写入了新文件."""
    target = Path(target)
    if target.exists() and not force:
        return False
    target.write_text(Path(sample_path).read_text(encoding="utf-8"), encoding="utf-8")
    return True


def review_courses(courses: list[Course]) -> Review:
    return review(Timetable(courses=courses))


def review_timetable(tt: Timetable) -> Review:
    return review(tt)


def holiday_notices(tt: Timetable, year: Optional[int] = None) -> HolidayReport:
    return holiday_report(tt, year=year)


def render_wallpapers(tt: Timetable, out_dir=None, which: str = "both",
                      background: str = "dusk", **options):
    return render_to_files(tt, out_dir=out_dir, which=which, background=background, **options)


def default_calendar_path() -> Path:
    return default_wallpaper_dir().parent / "课表.ics"


def export_calendar(tt: Timetable, out=None, reminder_minutes: int = 15) -> Path:
    target = Path(out) if out else default_calendar_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    return write_calendar(tt, target, reminder_minutes=reminder_minutes)


def file_signature(path) -> str:
    target = Path(path)
    return hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else ""


def import_text(text: str) -> tuple[list[Course], list[str]]:
    notes: list[str] = []
    return parse_pasted_text(text, notes), notes


def import_document(path) -> tuple[list[Course], list[str]]:
    """Text-only documents reuse the deterministic table parser."""
    from .documents import document_text
    return import_text(document_text(path))


def ai_settings():
    from .settings import load_ai_config
    return load_ai_config()


def save_ai_settings(config):
    from .settings import save_ai_config
    return save_ai_config(config)


def _save_current_verification(config):
    """A background request must not restore settings the user has since changed."""
    current = ai_settings()
    if current.signature == config.signature and config.vision_verified:
        current.verified_signature = config.verified_signature
        save_ai_settings(current)


def test_ai(config=None):
    from .ai import AIClient
    config = config or ai_settings()
    message = AIClient(config).test_vision()
    _save_current_verification(config)
    return message


def import_image(path, total_weeks=16, tiled=False, progress=None):
    from .ai import AIClient
    from .vision import recognize_image
    config = ai_settings()
    result = recognize_image(path, AIClient(config), total_weeks, tiled, progress)
    _save_current_verification(config)
    return result


def interpret_notification(tt, text):
    from .ai import AIClient
    from .notice import interpret_notice
    config = ai_settings()
    result = interpret_notice(text, tt, AIClient(config))
    _save_current_verification(config)
    return result


def notice_candidates(tt, intent):
    from .notice import find_candidates
    return find_candidates(tt, intent)


def notice_preview(tt, intent, selected, overrides=None):
    from .notice import preview_notice
    return preview_notice(tt, intent, selected, overrides)


def apply_notification(tt, preview):
    from .notice import accept_preview
    return accept_preview(tt, preview)


def make_busy_card(tt, name, weeks=None, campus=""):
    from .group import card_from_timetable
    return card_from_timetable(tt, name, weeks, campus)


def read_busy_card(text):
    from .group import decode_card
    return decode_card(text)


def group_free(cards, week, minimum_periods=2):
    from .group import common_free
    return common_free(cards, week, minimum_periods)


def export_busy_card(card, path):
    from .group import save_card
    return save_card(card, path)


def export_group_heatmap(result, path):
    from .group import render_heatmap
    return render_heatmap(result, path)


def export_group_meeting(result, window, title, path, start=None, end=None):
    from .group import export_meeting
    return export_meeting(result, window, title, path, start, end)


def export_poster(tt, path, week=None):
    from .poster import export_poster as generate
    return generate(tt, path, week)


def export_share_card(tt, path, week=None):
    from .poster import export_share_card as generate
    return generate(tt, path, week)


def agenda(tt, day=None):
    from .agenda import agenda_text
    return agenda_text(tt, day)


def preview_wallpaper(tt, **options):
    from .render import render_wallpaper
    return render_wallpaper(tt, **options)


def current_week(tt):
    from .agenda import week_number
    return week_number(tt)


def set_desktop_wallpaper(path):
    """Called only for an explicit wallpaper-setting action."""
    import os
    if os.name != "nt":
        raise ValueError("自动设为桌面壁纸目前仅支持 Windows, 请手动设置.")
    import ctypes
    target = str(Path(path).resolve())
    if not Path(target).is_file():
        raise ValueError("壁纸文件不存在.")
    if not ctypes.windll.user32.SystemParametersInfoW(20, 0, target, 3):
        raise ValueError("系统未能设置壁纸, 请手动选择生成的图片.")


def course_from_fields(name, day, periods, weeks="", room="", original=None):
    from .model import parse_day, parse_periods
    weekday = parse_day(day)
    span = parse_periods(periods)
    if not str(name).strip() or weekday is None or span is None or not 1 <= span[0] <= span[1] <= 12:
        raise ValueError("请填写课程名称, 星期以及 1-12 范围内的节次.")
    course = copy.deepcopy(original) if original else Course(str(name).strip(), weekday, span[0], span[1])
    course.name, course.day, course.start, course.end = str(name).strip(), weekday, span[0], span[1]
    course.weeks, course.room = str(weeks).strip(), str(room).strip()
    return course


def configure_semester(tt, term, start, total, clocks, timezone="Asia/Shanghai"):
    from datetime import date, time
    from .semester import SemesterCalendar
    result = copy.deepcopy(tt)
    try:
        result.term = str(term).strip()
        result.semester_start = date.fromisoformat(str(start).strip())
        result.weeks_total = int(total)
        if not 1 <= result.weeks_total <= 104:
            raise ValueError("学期总周数应在 1-104 之间.")
        result.timezone = str(timezone).strip()
        parsed = {}
        for period, text in clocks.items():
            if not str(text).strip():
                continue
            a, b = str(text).strip().split("-")
            first, last = time.fromisoformat(a.strip()), time.fromisoformat(b.strip())
            if last <= first:
                raise ValueError("结束时间必须晚于开始时间.")
            parsed[int(period)] = (first, last)
        for first, second in zip(sorted(parsed), sorted(parsed)[1:]):
            if parsed[first][1] > parsed[second][0]:
                raise ValueError("节次时间相互重叠, 请核对作息表.")
        result.period_times = parsed
        SemesterCalendar.from_timetable(result)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"学期设置有误: {exc}") from exc
    return result


def load_adapter(path):
    import yaml
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("适配配置最外层应为对象.")
    return value


def member_timetable(courses, semester_source):
    result = copy.deepcopy(semester_source)
    result.courses = copy.deepcopy(courses)
    result.warnings = []
    return result


def point_grid_path():
    from .point_grid import resource_path
    return resource_path()


def point_grid_defaults(tt=None, members=(), week=1):
    from .point_grid import page_defaults
    return page_defaults(tt, members, week)


def export_point_grid(path, tt=None, members=(), week=1):
    from .point_grid import export_page
    return export_page(path, tt, members, week)
