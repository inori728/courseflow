"""应用用例层: 给 CLI(以及后续 GUI)提供不依赖界面的操作.

CLI 只负责参数和文字输出; 真正读写课表、校对、出图的流程放在这里.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .audit import Review, review
from .ics import write_calendar
from .model import Course, Timetable
from .parsing import parse_pasted_text, parse_table_file, read_clipboard_text
from .render import default_wallpaper_dir, render_to_files
from .source import load_source, save_source


def load_timetable(path) -> Timetable:
    return load_source(path)


def import_table(path) -> tuple[list[Course], list[str]]:
    notes: list[str] = []
    courses = parse_table_file(path, notes)
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
    tt = Timetable(courses=courses)
    if not target.exists():
        return tt

    try:
        old = load_source(target)
    except Exception:
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
    for course in courses:
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


def save_timetable(tt: Timetable, target) -> Optional[Path]:
    """写回课表; 旧文件存在时先备份为 .bak, 返回备份路径."""
    target = Path(target)
    backup = None
    if target.exists():
        backup = target.with_name(target.name + ".bak")
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
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


def render_wallpapers(tt: Timetable, out_dir=None, which: str = "both",
                      background: str = "dusk"):
    return render_to_files(tt, out_dir=out_dir, which=which, background=background)


def default_calendar_path() -> Path:
    return default_wallpaper_dir().parent / "课表.ics"


def export_calendar(tt: Timetable, out=None, reminder_minutes: int = 15) -> Path:
    target = Path(out) if out else default_calendar_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    return write_calendar(tt, target, reminder_minutes=reminder_minutes)
