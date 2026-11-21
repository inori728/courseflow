"""Local CourseFlow service for the DeepSeek Harness companion plugin."""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta, timezone
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import time

from PIL import Image

from . import service
from .agenda import agenda_text, local_today, week_number
from .backgrounds import BACKGROUNDS, make_background
from .group import (FreeWindow, apply_group_clocks, available_slot, group_clock_defaults, group_clock_options,
                    pick_grid_slot, require_free_slot, write_meeting)
from .guide import usage_guide
from .harness_commands import (SHORTCODE, _WEEK, adjust_intent, command_kind, course_search_key, formats_for, group_minimum,
                               next_course_name, wants_change, week_for)
from .harness_controls import run_control
from .harness_planning import HarnessPlanning, schedule_command
from .model import DAYS, Timetable
from .notice import NoticeIntent
from .planning import continuous_slots
from .render import wallpaper_size
from .schedule import resolve_timetable
from .semester import SCHOOL_CLOCKS, SemesterCalendar, _tzinfo
from .settings import AIConfig, AI_REQUIRED, atomic_text, settings_dir
from .source import save_source, timetable_from_mapping, timetable_mapping
from .todos import todo_command, todo_list

IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
TABLES = {".yaml", ".yml", ".csv", ".xlsx", ".docx", ".pdf"}
EXPORTS = ("yaml", "ics", "desktop", "phone", "pdf", "png")
WALLPAPER_FORMATS = {"desktop", "phone"}
BACKGROUND_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
TOKEN = re.compile(r"[a-f0-9]{32}")


class SettingsRequired(ValueError):
    pass


def _span(timetable, first, last):
    times = timetable.period_times
    if first in times and last in times:
        return f"{times[first][0]:%H:%M}-{times[last][1]:%H:%M}"
    return ""


def _clock_fields(period_times):
    return {str(period): f"{start:%H:%M}-{end:%H:%M}" for period, (start, end) in period_times.items()}


def _semester_data(tt):
    return {
        "term": tt.term, "start": tt.semester_start.isoformat() if tt.semester_start else "",
        "total": tt.weeks_total, "timezone": tt.timezone,
        "clocks": _clock_fields(tt.period_times),
    }


def _with_semester(tt, details):
    if not isinstance(details, dict):
        raise ValueError("请核对学期信息.")
    return service.configure_semester(tt, details.get("term", ""), details.get("start", ""),
                                     details.get("total", 16), details.get("clocks", {}), details.get("timezone", "Asia/Shanghai"))


def _table_data(tt, editable=False):
    info = _semester_data(tt)
    rows = []
    for index, course in enumerate(tt.courses):
        editable_row = {
            "name": course.name, "day": course.day_name, "periods": f"{course.start}-{course.end}",
            "weeks": course.weeks, "room": course.room, "kind": course.kind, "index": index,
        }
        rows.append(editable_row)
    return {"semester": info, "courses": rows, "editable": editable,
            "warnings": tt.warnings, "school_clocks": SCHOOL_CLOCKS}


def _occurrence_data(tt, occ, calendar=None):
    value = {
        "name": occ.name, "week": occ.week, "day": DAYS[occ.day], "start": occ.start,
        "end": occ.end, "room": occ.room, "clock": _span(tt, occ.start, occ.end),
        "kind": occ.course.kind,
    }
    if calendar and occ.week:
        date_value = calendar.date_for(occ.week, occ.day)
        value["date"] = date_value.isoformat()
        zone = _tzinfo(tt.timezone)[0]
        if occ.start in tt.period_times:
            begin = datetime.combine(date_value, tt.period_times[occ.start][0], zone)
            value["startsAt"] = int(begin.timestamp() * 1000)
        if occ.end in tt.period_times:
            end = datetime.combine(date_value, tt.period_times[occ.end][1], zone)
            value["endsAt"] = int(end.timestamp() * 1000)
    return value


def _wallpaper_options(value):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("请选择有效的壁纸背景\u3002")
    background = value.get("background", "dusk")
    if isinstance(background, str) and background in BACKGROUNDS:
        return {"preset": background, "label": BACKGROUNDS[background]}, None
    if background != "custom":
        raise ValueError("请选择有效的壁纸背景\u3002")

    selected = value.get("image")
    if not isinstance(selected, dict):
        raise ValueError("请选择一张本地背景图片\u3002")
    name = Path(str(selected.get("name", ""))).name
    if Path(name).suffix.lower() not in BACKGROUND_SUFFIXES:
        raise ValueError("请选择 PNG\u3001JPG\u3001WebP 或 BMP 背景图片\u3002")
    data = selected.get("base64")
    if not isinstance(data, str) or not data:
        raise ValueError("未读取到背景图片\uff0c请重新选择\u3002")
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("背景图片最多 12 MB\uff0c请选择较小的图片\u3002")
    try:
        raw = base64.b64decode(data, validate=True)
        with Image.open(BytesIO(raw), formats=("PNG", "JPEG", "WEBP", "BMP")) as picture:
            picture.verify()
    except (ValueError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("无法读取背景图片\uff0c请换一张可打开的图片\u3002") from exc
    return {"preset": "dusk", "label": name}, raw


@contextmanager
def _files(payload, scratch):
    files = payload.get("files", [])
    if not isinstance(files, list) or len(files) > 20:
        raise ValueError("每次最多添加 20 份成员资料.")
    if not files:
        yield []
        return
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        result = []
        for index, item in enumerate(files):
            name = Path(str(item["name"])).name
            suffix = Path(name).suffix.lower()
            if suffix not in IMAGES | TABLES | {".busycard", ".txt"}:
                raise ValueError(f"暂不支持这个文件格式: {name}")
            if "path" in item:
                path = Path(item["path"])
            else:
                path = Path(directory) / f"{index}{suffix}"
                data = str(item["base64"])
                if len(data) > 20_000_000:
                    raise ValueError("附件过大, 请分批添加或用斜杠命令.")
                path.write_bytes(base64.b64decode(data, validate=True))
            if not path.is_file() or path.stat().st_size > 40 * 1024 * 1024:
                raise ValueError(f"文件不存在或超过 40 MB: {name}")
            result.append((path, name, suffix))
        yield result


class Harness:
    def __init__(self, source=None):
        self.source = Path(source).resolve() if source is not None else None
        self.root = settings_dir() / "harness"
        self.drafts = self.root / "drafts"
        self.exports = self.root / "exports"
        self.planning = HarnessPlanning(self)

    def run(self, action, payload):
        if action == "guide":
            return usage_guide()
        if action in {"assistant", "assistant_choose"}:
            from .assistant import Assistant
            assistant = Assistant(self)
            return assistant.send(payload) if action == "assistant" else assistant.choose(payload)
        handlers = {
            "status": self.status, "settings": self.settings, "save_settings": self.save_settings,
            "request": self.request, "agenda": self.agenda, "prepare": self.prepare,
            "semester_week": self.semester_week, "save_semester_week": self.save_semester_week,
            "wallpaper_background_preview": self.wallpaper_background_preview,
            "preview": self.preview, "commit": self.commit, "undo": self.undo, "group_prepare": self.group_prepare,
            "group_search": self.group_search, "group_refresh": self.group_refresh, "activity": self.activity, "point_grid": self.point_grid,
            "todos": todo_list, "schedule": self.planning.run,
            "activity_preview": self.activity_preview, "activity_clocks": self.activity_clocks,
            "todo_reserve": self.reserve_todo,
        }
        if action not in handlers:
            raise ValueError("未知的 CourseFlow 操作.")
        if action in {"prepare", "group_prepare"}:
            with _files(payload, self.root / "tmp") as files:
                return handlers[action](payload, files)
        return handlers[action](payload)

    def source_path(self):
        if self.source is not None:
            return self.source
        bound = os.environ.get("COURSEFLOW_SOURCE")
        return Path(bound).resolve() if bound else service.default_gui_source().resolve()

    def load(self):
        path = self.source_path()
        tt, signature = service.load_timetable_snapshot(path)
        return path, tt, signature

    def _undo_path(self, source):
        key = hashlib.sha256(os.fsencode(os.path.normcase(str(source)))).hexdigest()
        return self.root / "undo" / f"{key}.json"

    def status(self, payload):
        path = self.source_path()
        undo_path = self._undo_path(path)
        signature = service.file_signature(path)
        result = {"present": bool(signature), "source": path.name, "signature": signature, "watch_path": str(path),
                  "watch_undo_path": str(undo_path)}
        if not signature or payload.get("signature") == signature and not payload.get("full"):
            result["undo"] = service.timetable_undo_status(undo_path, signature)
            return result
        tt, signature = service.load_timetable_snapshot(path)
        now = datetime.now(timezone.utc)
        today = local_today(tt, now)
        tomorrow = datetime.combine(today + timedelta(days=1), datetime.min.time(), _tzinfo(tt.timezone)[0])
        result.update(signature=signature, date=today.isoformat(), term=tt.term, weeks_total=tt.weeks_total,
                      semester_start=tt.semester_start.isoformat() if tt.semester_start else "",
                      today=[], upcoming=None, warnings=tt.warnings, undo=service.timetable_undo_status(undo_path, signature),
                      next_day_at=int(tomorrow.timestamp() * 1000))
        if not tt.semester_start or tt.semester_start.weekday() != 0:
            result["note"] = "设置当前周次后\uff0c可以查看今日安排和下一节课\u3002"
            return result
        calendar = SemesterCalendar.from_timetable(tt)
        week = (today - calendar.start).days // 7 + 1
        result["week"] = week
        timestamp = int(now.timestamp() * 1000)
        upcoming = []
        for occ in resolve_timetable(tt, tt.weeks_total):
            if occ.week is None or not 1 <= occ.week <= tt.weeks_total or occ.week < week:
                continue
            day = calendar.date_for(occ.week, occ.day)
            if day < today:
                continue
            entry = _occurrence_data(tt, occ, calendar)
            if day == today:
                result["today"].append(entry)
            if entry.get("startsAt", 0) > timestamp or day > today:
                upcoming.append(entry)
        key = lambda entry: (entry["date"], entry["start"], entry["name"])
        result["today"].sort(key=key)
        if upcoming:
            result["upcoming"] = min(upcoming, key=key)
        if not tt.period_times:
            result["note"] = "请设置节次钟点, 再使用倒计时和提醒."
        return result

    def semester_week(self, payload):
        path, tt, signature = self.load()
        today = local_today(tt, datetime.now(timezone.utc))
        monday = (today - timedelta(days=today.weekday())).isoformat()
        week = week_number(tt, today) if tt.semester_start and tt.semester_start.weekday() == 0 else 0
        suggested = payload.get("suggested_week")
        if suggested is not None and (type(suggested) is not int or not 1 <= suggested <= tt.weeks_total):
            raise ValueError(f"请输入 1 到 {tt.weeks_total} 之间的周次.")
        token = self._draft({"type": "semester_week", "path": str(path), "signature": signature, "monday": monday})
        result = {"type": "semester_week", "token": token, "today": today.isoformat(), "monday": monday,
                  "current_week": week if 1 <= week <= tt.weeks_total else None, "weeks_total": tt.weeks_total}
        if suggested is not None:
            start = date.fromisoformat(monday) - timedelta(weeks=suggested - 1)
            result.update(suggested_week=suggested, message=f"第 1 周将设为 {start.isoformat()}. 核对后输入确认周次.")
        return result

    def save_semester_week(self, payload):
        token = payload.get("token")
        draft = self._get_draft(token, "semester_week")
        if draft.get("receipt"):
            return draft["receipt"]
        path = self._await_write(draft)
        tt = service.load_timetable(path)
        week = payload.get("week")
        if isinstance(week, bool) or not isinstance(week, int) or not 1 <= week <= tt.weeks_total:
            raise ValueError(f"请输入 1 到 {tt.weeks_total} 之间的周次\u3002")
        start = date.fromisoformat(draft["monday"]) - timedelta(weeks=week - 1)
        updated = start != tt.semester_start
        if updated:
            timetable = replace(tt, semester_start=start)
            SemesterCalendar.from_timetable(timetable)
            service.save_timetable(timetable, path, expected_signature=draft["signature"],
                                   undo_path=self._undo_path(path), undo_label="学期周次设置")
        result = {"type": "saved", "updated": updated, "files": [],
                  "message": f"学期周次已保存\u3002第 1 周周一为 {start.isoformat()}\u3002"}
        self._update_draft(token, {**draft, "receipt": result})
        return result

    def settings(self, _payload):
        try:
            config = service.ai_settings()
        except (OSError, ValueError):
            config = AIConfig()
        try:
            config.validate()
            ready = config.vision_verified
        except ValueError:
            ready = False
        return {"base_url": config.base_url, "model": config.model, "has_key": bool(config.api_key),
                "timeout": config.timeout, "verified": ready}

    def save_settings(self, payload):
        try:
            previous = service.ai_settings()
        except ValueError:
            previous = AIConfig()
        base_url = str(payload.get("base_url", "")).strip().rstrip("/")
        saved_key = previous.api_key if base_url == previous.base_url.rstrip("/") else ""
        config = AIConfig(
            base_url=base_url, model=str(payload.get("model", "")).strip(),
            api_key=str(payload.get("api_key") or ("" if payload.get("clear_key") else saved_key)).strip(),
            timeout=int(payload.get("timeout", 90)),
        )
        service.save_ai_settings(config)
        message = service.test_ai(config)
        return {**self.settings({}), "message": message}

    def require_vision(self):
        try:
            config = service.ai_settings()
            config.validate()
        except (OSError, ValueError) as exc:
            raise SettingsRequired(AI_REQUIRED) from exc
        if not config.vision_verified:
            raise SettingsRequired(AI_REQUIRED + " 请先在 AI 接口设置中保存并自检.")
        return config

    def ai_self_check(self):
        try:
            config = service.ai_settings()
            config.validate()
        except (OSError, ValueError) as exc:
            raise SettingsRequired(AI_REQUIRED) from exc
        return {"type": "settings", "message": service.test_ai(config)}

    def agenda(self, payload):
        _, tt, _ = self.load()
        text = str(payload.get("text", ""))
        name = next_course_name(text)
        if name:
            return self.next_course(tt, name)
        if "下一节" in text or "下节" in text:
            return {"type": "agenda", "upcoming": self.status({"full": True}).get("upcoming")}
        if payload.get("week") is not None or re.search(r"(?:第.+?周|本周|这周|下周|上周)", text):
            week = week_for(f"第{payload['week']}周" if payload.get("week") is not None else text, tt)
            return self.week_agenda(tt, week)
        day = local_today(tt) + timedelta(days=1 if "明天" in text else 0)
        return {"type": "agenda", "message": agenda_text(tt, day)}

    def next_course(self, tt, name):
        key = course_search_key(name)
        matched = {course.name for course in tt.courses if course.kind != "activity"
                   and key in course_search_key(course.name)}
        exact = {item for item in matched if course_search_key(item) == key}
        matched = exact or matched
        if not matched:
            return {"type": "agenda", "message": f"课表中未找到 {name}."}
        if len(matched) > 1:
            return {"type": "agenda", "message": "找到多门课, 请给出完整课名: " + " / ".join(sorted(matched))}
        name = next(iter(matched))
        calendar = SemesterCalendar.from_timetable(tt)
        now = datetime.now(_tzinfo(tt.timezone)[0])
        entries = []
        for occ in resolve_timetable(tt, tt.weeks_total):
            if occ.name != name or occ.course.kind == "activity" or not occ.week:
                continue
            when = calendar.date_for(occ.week, occ.day)
            if when < now.date():
                continue
            item = _occurrence_data(tt, occ, calendar)
            clock = tt.period_times.get(occ.start)
            if when == now.date() and clock and clock[0] < now.time():
                continue
            entries.append(item)
        if not entries:
            return {"type": "agenda", "message": f"{name} 没有后续已确认的课次."}
        upcoming = min(entries, key=lambda item: (item["date"], item["start"], item["end"], item["room"]))
        periods = str(upcoming["start"]) if upcoming["start"] == upcoming["end"] else f"{upcoming['start']}-{upcoming['end']}"
        message = " ".join(filter(None, (upcoming["name"], upcoming["date"], upcoming["day"], f"第 {periods} 节",
                                         upcoming["clock"], upcoming["room"] or "教室待确认")))
        return {"type": "agenda", "upcoming": upcoming, "message": message}

    def week_agenda(self, tt, week):
        data = service.week_calendar_data(tt, week)
        days = [{"label": label, "date": data["dates"][i].isoformat() if data["dates"] else "", "courses": []}
                for i, label in enumerate(DAYS)]
        lines = [f"第 {week} 周课表"]
        for occ in sorted(data["courses"], key=lambda item: (item.day, item.start, item.name)):
            item = _occurrence_data(tt, occ)
            days[occ.day]["courses"].append(item)
            slot = f"{item['day']} {item['clock']}" if item["clock"] else occ.slot_text()
            lines.append(" · ".join(filter(None, (slot, item["name"], item["room"]))))
        warnings = ["在侧栏「课表」页点「设置当前周次」\uff0c即可显示每周日期\u3002"] if data["date_note"] else []
        if data["unknown"]:
            warnings.append("周次待确认的课程有 " + "\u3001".join(data["unknown"]))
        if len(lines) == 1:
            lines.append("本周没有已确认的课程.")
        return {"type": "agenda", "week": week, "weeks_total": tt.weeks_total, "days": days,
                "warnings": warnings, "message": "\n".join(lines + warnings)}

    def request(self, payload):
        text = str(payload.get("text", "")).strip()
        if len(text) > 250000:
            raise ValueError("指令过长, 请改用文件或分批上传.")
        mode = payload.get("mode")
        if mode is not None:
            if mode in ("import", "adjust", "export"):
                return self.run("prepare", payload)
            if mode == "group":
                return self.run("group_prepare", payload)
            if mode == "agenda":
                return self.run("agenda", payload)
            raise ValueError("未知的侧栏操作.")
        if next_course_name(text):
            return self.run("agenda", payload)
        if re.match(r"^(?:添加|删除|查看|完成|取消完成|重开|重新打开)(?:待办|待做任务)", text):
            tt = self.load()[1] if self.source_path().is_file() else Timetable()
            return todo_list(todo_command(text, local_today(tt)))
        operation = schedule_command(text)
        if operation:
            return self.planning.command(operation, payload, text)
        controlled = run_control(self, payload, text)
        if controlled is not None:
            return controlled
        action = "prepare" if payload.get("intent") or payload.get("formats") else command_kind(text, len(payload.get("files", [])))
        return self.run(action, payload)

    def _draft(self, value, *, wallpaper_image=None):
        self.drafts.mkdir(parents=True, exist_ok=True)
        for path in self.drafts.iterdir():
            if path.suffix not in {".json", ".background"}:
                continue
            try:
                if time.time() - path.stat().st_mtime > 86400:
                    path.unlink(missing_ok=True)
            except OSError:
                continue
        token = secrets.token_hex(16)
        if wallpaper_image is not None:
            (self.drafts / f"{token}.background").write_bytes(wallpaper_image)
            value["wallpaper"]["image_token"] = token
        self._update_draft(token, value)
        return token

    def _update_draft(self, token, value):
        atomic_text(self.drafts / f"{token}.json", json.dumps(value, ensure_ascii=False, default=str))

    def _get_draft(self, token, expected):
        if not isinstance(token, str) or not TOKEN.fullmatch(token):
            raise ValueError("请先生成新的预览或查询结果.")
        path = self.drafts / f"{token}.json"
        if not path.is_file() or time.time() - path.stat().st_mtime > 86400:
            raise ValueError("这份预览已过期, 请重新发起.")
        value = json.loads(path.read_text(encoding="utf-8"))
        expected_types = (expected,) if isinstance(expected, str) else expected
        if value["type"] not in expected_types:
            raise ValueError("请选择当前操作对应的预览.")
        return value

    def _background_path(self, wallpaper):
        token = wallpaper.get("image_token")
        if token is None:
            return None
        if isinstance(token, str) and TOKEN.fullmatch(token):
            path = self.drafts / f"{token}.background"
            if path.is_file():
                return path
        raise ValueError("背景图片的预览已过期\uff0c请重新选择\u3002")

    def _await_write(self, draft):
        path = self.source_path()
        if draft["path"] != str(path) or draft["signature"] != service.file_signature(path):
            raise ValueError("共用课表在预览后已更新, 请刷新并重新预览.")
        return path

    def _confirmation(self, draft, tt, overwrite):
        return self._draft({**draft, "type": "confirmed", "data": timetable_mapping(tt), "overwrite": overwrite})

    def _out(self):
        self.exports.mkdir(parents=True, exist_ok=True)
        target = self.exports / secrets.token_hex(16)
        target.mkdir()
        return target

    def _import_file(self, item, basis):
        path, name, suffix = item
        if suffix in {".yaml", ".yml"}:
            return service.load_timetable(path), False
        if suffix in IMAGES:
            self.require_vision()
            draft = service.import_image(path, basis.weeks_total)
            tt = service.member_timetable(draft.courses, basis)
            tt.warnings.extend(draft.notes)
            return tt, True
        if suffix in {".docx", ".pdf"}:
            courses, warnings = service.import_document(path)
        elif suffix == ".txt":
            courses, warnings = service.import_text(path.read_text(encoding="utf-8-sig"))
        else:
            courses, warnings = service.import_table(path)
        if not courses:
            raise ValueError(f"没有从 {name} 导入课程, 请核对文件内容.")
        tt = service.member_timetable(courses, basis)
        tt.warnings.extend(warnings)
        return tt, True

    def prepare(self, payload, files):
        if payload.get("wallpaper_attachment"):
            if len(files) != 1 or files[0][2] not in BACKGROUND_SUFFIXES:
                raise ValueError("请只附上一张壁纸背景图片.")
            path, name, _ = files[0]
            if path.stat().st_size > 12 * 1024 * 1024:
                raise ValueError("壁纸背景最多 12 MB.")
            image = {"base64": base64.b64encode(path.read_bytes()).decode("ascii"), "name": name}
            payload = {**payload, "wallpaper": {"background": "custom", "image": image}}
            files = []
        if len(files) > 1:
            raise ValueError("请选一份课表作为调课或导出来源. 多人课表请用组队查空闲.")
        mode = payload.get("mode")
        importing = mode == "import"
        if importing and not files:
            raise ValueError("请选择要导入的课表文件或截图.")
        path = self.source_path()
        basis = Timetable()
        signature = ""
        if path.is_file():
            basis, signature = service.load_timetable_snapshot(path)
        text = str(payload.get("text", ""))
        tt, editable = self._import_file(files[0], basis) if files else (basis, False)
        if not tt.courses:
            raise ValueError("没有可用的课程, 请先打开已保存的课表或附上课表文件.")
        overwrite = importing or not files or bool(re.search(r"(?:更新|覆盖|写回|改到)\s*(?:我的|当前|共用的)?课表", text))
        if files and overwrite and editable:
            imported = tt
            tt = service.merge_import(imported.courses, basis)
            tt.warnings.extend(imported.warnings)
        if payload.get("intent") is not None and not isinstance(payload["intent"], dict):
            raise ValueError("调课字段有误.")
        change = mode == "adjust" or payload.get("intent") is not None or wants_change(text)
        formats = payload.get("formats", formats_for(text))
        if not isinstance(formats, list) or any(fmt not in EXPORTS for fmt in formats):
            raise ValueError("请选择有效的导出格式.")
        if not change and not formats and files and not importing:
            formats = ["yaml"]
        wallpaper, wallpaper_image = (None, None)
        if WALLPAPER_FORMATS.intersection(formats):
            wallpaper, wallpaper_image = _wallpaper_options(payload.get("wallpaper"))
        options = {
            "formats": list(dict.fromkeys(formats)),
            "theme": "light" if "浅色" in text else "dark",
            "wallpaper_week": None,
            "wallpaper": wallpaper,
        }
        reference = payload.get("wallpaper_week_reference")
        if isinstance(reference, str) and reference:
            options["wallpaper_week"] = week_for(reference, tt)
        elif isinstance(payload.get("wallpaper_week"), int):
            options["wallpaper_week"] = payload["wallpaper_week"]
        token = self._draft({
            "type": "change", "path": str(path), "signature": signature, "overwrite": overwrite,
            "data": timetable_mapping(tt, sorted_courses=False), "warnings": tt.warnings, "text": text,
            "change": change, "intent": payload.get("intent"), "editable": editable,
            "imported": bool(files), **options,
        }, wallpaper_image=wallpaper_image)
        info = _table_data(tt, editable)
        if not tt.period_times:
            info["semester"]["clocks"] = {str(p): value for p, value in SCHOOL_CLOCKS.items()}
        return {"type": "prepare", "token": token, "table": info, "formats": options["formats"],
                "change": change, "overwrite": overwrite, "source": path.name, "imported": bool(files),
                "wallpaper_background": wallpaper["label"] if wallpaper else ""}

    def _edited(self, tt, editable, payload):
        if payload.get("semester") is not None:
            tt = _with_semester(tt, payload["semester"])
        if editable and isinstance(payload.get("courses"), list):
            rows = payload["courses"]
            if len(rows) > 500:
                raise ValueError("课程过多, 请分次导入.")
            if not rows:
                raise ValueError("至少保留一条课程.")
            originals = {i: course for i, course in enumerate(tt.courses)}
            tt.courses = [service.course_from_fields(row["name"], row["day"], row["periods"],
                         row.get("weeks", ""), row.get("room", ""), originals.get(row.get("index"))) for row in rows]
        return tt

    def command_preview(self, token, fields):
        if set(fields) - {"semester", "courses", "selected"}:
            raise ValueError("课表编辑支持 semester, courses 和 selected 字段.")
        changes = self._get_draft(token, "change").get("preview_fields", {})
        return self.preview({**changes, **fields, "token": token})

    def preview(self, payload):
        token = payload.get("token")
        draft = self._get_draft(token, "change")
        original = timetable_from_mapping(draft["data"])
        tt = self._edited(original, draft["editable"], payload)
        draft["preview_fields"] = {key: payload[key] for key in ("semester", "courses", "selected") if key in payload}
        self._update_draft(token, draft)
        intent_data = draft["intent"]
        wallpaper = draft.get("wallpaper") or {}
        result = {"type": "preview", "token": token, "change": draft["change"], "formats": draft["formats"],
                  "overwrite": draft["overwrite"], "source": Path(draft["path"]).name, "conflicts": [], "rows": [],
                  "wallpaper_background": wallpaper.get("label", "")}
        if draft["change"]:
            if intent_data is None:
                intent_data = adjust_intent(draft["text"], tt)
                if intent_data is None:
                    self.require_vision()
                    intent_data = asdict(service.interpret_notification(tt, draft["text"]))
                    if intent_data["source_day"] is not None:
                        intent_data["source_day"] += 1
                    if intent_data["target_day"] is not None:
                        intent_data["target_day"] += 1
                draft["intent"] = intent_data
                self._update_draft(token, draft)
            intent = NoticeIntent.from_payload(intent_data, tt.weeks_total)
            candidates = service.notice_candidates(tt, intent)
            if not candidates:
                raise ValueError("找不到符合原周次 / 星期 / 节次的课程, 请核对后重试.")
            result["candidates"] = [
                {"id": item.token, "label": item.describe(), **_occurrence_data(tt, item.occurrence)}
                for item in candidates
            ]
            selected = payload.get("selected")
            if selected is None and len(candidates) == 1:
                selected = [candidates[0].token]
            if not selected:
                return result
            chosen = [item for item in candidates if item.token in selected]
            if len(chosen) != len(set(selected)):
                raise ValueError("候选课次已变化, 请重新选择.")
            preview = service.notice_preview(tt, intent, chosen)
            result["selected"] = selected
            result["conflicts"] = preview.new_conflicts
            result["notes"] = preview.warnings
            for item, (before, after) in zip(chosen, preview.rows):
                old = item.occurrence
                old_course = preview.timetable.courses[item.course_index]
                change = next((entry for entry in old_course.changes if entry.week == item.source_week), None)
                result["rows"].append({
                    "before": f"{before} {_span(tt, old.start, old.end)}".strip(),
                    "after": f"{after} {_span(tt, change.start, change.end) if change else ''}".strip(),
                })
            tt = preview.timetable
            if draft["editable"] and not result["conflicts"]:
                result["conflicts"] = service.review_timetable(tt).conflicts
        else:
            if draft["editable"] or (draft["imported"] and draft["overwrite"]):
                result["conflicts"] = service.review_timetable(tt).conflicts
        if draft["overwrite"] and not (draft["change"] or draft["imported"]):
            result["overwrite"] = False
        result["warnings"] = service.review_timetable(tt).issues
        if "ics" in result["formats"]:
            calendar = SemesterCalendar.from_timetable(tt)
            for occ in resolve_timetable(tt, tt.weeks_total):
                if occ.week is None:
                    raise ValueError(f"'{occ.name}' 的周次待确认, 请先补齐再导出日历.")
                calendar.times_for(occ.start, occ.end)
        if not result["conflicts"]:
            render_options = self._wallpaper_render_options(draft)
            result["wallpaper_previews"] = {
                fmt: self._wallpaper_preview(tt, fmt, render_options)
                for fmt in draft["formats"] if fmt in WALLPAPER_FORMATS
            }
            background = render_options["bg_image"]
            if background is not None:
                # The confirmation has its own lifetime and reuses the selected image.
                os.utime(background, None)
            result["confirmation"] = self._confirmation(draft, tt, result["overwrite"])
        return result

    def wallpaper_background_preview(self, payload):
        background, fmt = payload.get("background"), payload.get("format")
        if not isinstance(background, str) or background not in BACKGROUNDS or fmt not in ("desktop", "phone"):
            raise ValueError("请选择有效的壁纸背景和尺寸\u3002")
        dimensions = wallpaper_size(fmt)
        scale = min(1, 960 / max(dimensions))
        size = tuple(max(2, round(length * scale)) for length in dimensions)
        with BytesIO() as buffer:
            make_background(background, size, fmt).save(buffer, format="PNG")
            return {"base64": base64.b64encode(buffer.getvalue()).decode("ascii")}

    @staticmethod
    def _wallpaper_preview(tt, fmt, options):
        with service.preview_wallpaper(tt, size=wallpaper_size(fmt), layout=fmt, **options) as image, BytesIO() as buffer:
            image.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            image.convert("RGB").save(buffer, format="JPEG", quality=91, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode("ascii")

    def _wallpaper_render_options(self, draft):
        wallpaper = draft.get("wallpaper") or {}
        return {"theme": draft["theme"], "week": draft["wallpaper_week"],
                "background": wallpaper.get("preset", "dusk"), "bg_image": self._background_path(wallpaper)}

    def _export(self, tt, draft):
        formats = draft["formats"]
        if not formats:
            return []
        wallpaper_options = self._wallpaper_render_options(draft)
        out = self._out()
        files = []
        for fmt in formats:
            if fmt == "yaml":
                target = out / "课表.yaml"
                save_source(tt, target)
            elif fmt == "ics":
                target = service.export_calendar(tt, out / "课表.ics")
            elif fmt in {"pdf", "png"}:
                target = service.export_poster(tt, out / f"课表挂图.{fmt}", draft["wallpaper_week"])
            else:
                target = service.render_wallpapers(tt, out_dir=out, which=fmt, **wallpaper_options)[0][0]
            files.append({"name": target.name, "id": f"{out.name}/{target.name}"})
        return files

    def commit(self, payload):
        token = payload.get("token")
        draft = self._get_draft(token, "confirmed")
        if draft.get("receipt"):
            return draft["receipt"]
        path = self._await_write(draft) if draft["overwrite"] else None
        tt = timetable_from_mapping(draft["data"])
        files = self._export(tt, draft)
        if path:
            label = draft.get("write_label") or ("调课" if draft["change"] else "导入课表")
            service.save_timetable(tt, path, expected_signature=draft["signature"],
                                   undo_path=self._undo_path(path), undo_label=label)
            service.remember_current_source(path)
        result = {"type": "saved", "updated": path is not None, "files": files,
                  "message": "共用课表已保存." if path else "文件已生成."}
        self._update_draft(token, {**draft, "receipt": result})
        return result

    def undo(self, payload):
        path = self.source_path()
        label = service.undo_timetable(path, self._undo_path(path), payload.get("token"))
        return {"type": "saved", "updated": True, "files": [], "message": f"已撤销上一次{label}\u3002"}

    def group_prepare(self, payload, files):
        text = str(payload.get("text", ""))
        codes = payload.get("shortcodes", [])
        if not isinstance(codes, list) or any(not isinstance(code, str) for code in codes):
            raise ValueError("请核对忙闲卡短码.")
        order = payload.get("member_order", ["file"] * len(files) + ["code"] * len(codes))
        if (not isinstance(order, list) or len(order) != len(files) + len(codes)
                or order.count("file") != len(files) or order.count("code") != len(codes)):
            raise ValueError("请核对已添加的成员资料.")
        pasted = re.findall(SHORTCODE, text)
        if len(set(codes + pasted)) > 100:
            raise ValueError("组队最多支持 100 位成员.")
        basis = self.load()[1] if self.source_path().is_file() else Timetable()
        members = []
        uploaded_cards = []
        seen_codes = set()
        file_items, code_items = iter(files), iter(codes + pasted)
        for kind in order + ["code"] * len(pasted):
            if kind == "file":
                item = next(file_items)
                path, name, suffix = item
                code = path.read_text(encoding="utf-8-sig").strip() if suffix in {".busycard", ".txt"} else ""
                if suffix != ".busycard" and not code.startswith("CF1."):
                    tt, editable = self._import_file(item, basis)
                    members.append({"name": Path(name).stem[:80], "timetable": timetable_mapping(tt, sorted_courses=False),
                                    "editable": editable, "warnings": tt.warnings})
                    continue
            else:
                code = next(code_items).strip()
            if code in seen_codes:
                continue
            seen_codes.add(code)
            card = service.read_busy_card(code)
            uploaded_cards.append(card)
            members.append({"name": card.name, "card": code})
        if len(members) > 100:
            raise ValueError("组队最多支持 100 位成员.")
        include = payload.get("include_self", bool(re.search(r"和我|加上我|我的课表|包括我|算上我", text)))
        if not members and not include:
            raise ValueError("请添加成员课表 / 忙闲卡文件 / CF1 短码.")
        try:
            anchor = timetable_from_mapping(members[0]["timetable"]) if members and "timetable" in members[0] else basis
            shared_weeks = set()
            if members and "card" in members[0]:
                first = uploaded_cards[0]
                anchor = Timetable(semester_start=first.semester_start, weeks_total=104, timezone=first.timezone)
                specified_week = re.search(rf"{_WEEK}|本周|这周|上周|下周|当前周", text)
                if len(uploaded_cards) == len(members) and not specified_week:
                    shared_weeks = set(first.busy)
                    for card in uploaded_cards[1:]:
                        offset = (card.semester_start - first.semester_start).days // 7
                        shared_weeks.intersection_update(week + offset for week in card.busy)
            week = next(iter(shared_weeks)) if len(shared_weeks) == 1 else week_for(text, anchor)
        except ValueError:
            week = ""
        minimum, minutes = group_minimum(text)
        defaults = {"week": week, "minimum": minimum, "minutes": minutes, "include_self": bool(include)}
        token = self._draft({"type": "group", "members": members, "plan_request": payload.get("plan_request"),
                             "review_defaults": defaults})
        warning = ""
        if payload.get("search_now") is True and len(uploaded_cards) == len(members):
            try:
                return self.confirm_group(token, {})
            except ValueError as exc:
                warning = str(exc)
        card_rows = iter(uploaded_cards)
        rows = []
        for member in members:
            if "timetable" in member:
                tt = timetable_from_mapping(member["timetable"])
                row = _table_data(tt, member["editable"])
                if not tt.period_times:
                    row["semester"]["clocks"] = {str(p): val for p, val in SCHOOL_CLOCKS.items()}
                row["warnings"] = member["warnings"]
            else:
                card = next(card_rows)
                row = {"weeks": sorted(card.busy), "start": card.semester_start.isoformat(), "editable": False}
            rows.append({**row, "name": member["name"]})
        return {"type": "group_prepare", "token": token, "members": rows, "include_self": bool(include),
                "week": week, "minimum": minimum, "minutes": minutes, "can_include_self": bool(basis.courses),
                "warning": warning}

    def confirm_group(self, token, fields):
        if set(fields) - {"members", "week", "minutes", "minimum", "include_self", "self_name"}:
            raise ValueError("请核对组队编辑字段.")
        draft = self._get_draft(token, "group")
        options = {**draft.get("review_defaults", {}), **fields}
        if not options.get("week"):
            raise ValueError("请明确查询周次, 如确认组队 第7周.")
        options.setdefault("members", [{"name": member["name"]} for member in draft["members"]])
        return self.group_search({**options, "token": token})

    def _group_cards(self, draft, current=None, *, original=False):
        cards = []
        for item in draft["members"]:
            if "card" in item:
                cards.append(replace(service.read_busy_card(item["card"]), name=item["name"]))
            else:
                cards.append(service.make_busy_card(timetable_from_mapping(item["timetable"]), item["name"]))
        if draft.get("own"):
            if current is None:
                current = self.load()[1]
            cards.append(service.make_busy_card(current, draft["own"]))
        if not original and draft.get("group_clocks"):
            clocks = timetable_from_mapping({"period_times": draft["group_clocks"]}).period_times
            return apply_group_clocks(cards, clocks)
        return cards

    def _known_group_clocks(self, record, current):
        return next((card.period_times for card in self._group_cards(record, current, original=True)
                     if card.period_times), {})

    def _group_result(self, record, current=None, *, use_defaults=False):
        cards = self._group_cards(record, current)
        if use_defaults and not record.get("group_clocks"):
            clocks = group_clock_defaults(cards, current)
            if clocks:
                cards = apply_group_clocks(cards, clocks)
                record.update(group_clocks=_clock_fields(clocks), clock_source="default")
        result = service.group_free(cards, record["week"], record["minimum"])
        if record["minutes"]:
            if len(result.period_times) != 12:
                raise ValueError("要按分钟查找, 请先补齐 12 小节的起止时间.")
            result.windows = [FreeWindow(window.day, first, last) for window in result.windows
                              for first, last, start, end in continuous_slots(result, window.day, window.start, window.end)
                              if end - start >= timedelta(minutes=record["minutes"])]
        return result

    def group_search(self, payload):
        draft = self._get_draft(payload.get("token"), "group")
        edits = payload.get("members")
        if not isinstance(edits, list) or len(edits) != len(draft["members"]):
            raise ValueError("请核对成员名单.")
        for item, edit in zip(draft["members"], edits):
            name = str(edit.get("name", "")).strip()
            if not 1 <= len(name) <= 80:
                raise ValueError("请填写 1-80 字的成员名称.")
            item["name"] = name
            if "timetable" in item:
                tt = timetable_from_mapping(item["timetable"])
                tt = self._edited(tt, item["editable"], edit)
                item["timetable"] = timetable_mapping(tt)
        record = {**draft, "type": "group_result", "week": int(payload["week"]),
                  "minimum": int(payload.get("minimum", 2)), "minutes": int(payload.get("minutes", 0)),
                  "own": str(payload.get("self_name") or "我").strip() if payload.get("include_self") else ""}
        if not 0 <= record["minutes"] <= 1440:
            raise ValueError("最短时长应为 0-1440 分钟.")
        result = self._save_group_result(record)
        if draft.get("plan_request"):
            return self.planning.run({"operation": "find", "group_token": result["token"], "text": draft["plan_request"]})
        return result

    def group_refresh(self, payload):
        return self._save_group_result(self._get_draft(payload.get("token"), "group_result"))

    def _save_group_result(self, record):
        path = self.source_path()
        current, signature = service.load_timetable_snapshot(path) if path.is_file() else (None, "")
        group = self._group_result(record, current, use_defaults=True)
        record.update(path=str(path), signature=signature)
        token = self._draft(record)
        return {**self._group_view(token, group, record.get("clock_source", "")), "minutes": record["minutes"]}

    @staticmethod
    def _group_view(token, group, clock_source=""):
        return {
            "type": "group_result", "token": token, "week": group.week, "monday": group.monday.isoformat(),
            "dates": [(group.monday + timedelta(days=i)).isoformat() for i in range(7)],
            "names": group.names, "counts": group.counts, "windows": [asdict(window) for window in group.windows],
            "clocks": _clock_fields(group.period_times), "clock_source": clock_source,
            "warnings": group.warnings,
        }

    def reserve_todo(self, payload):
        item = todo_list({**payload, "operation": "lookup"})
        if item["done"]:
            raise ValueError("这条待办已完成, 需要安排时间时可先重新打开.")
        return {"type": "todo_reserve", "item": item, "group_token": payload.get("group_token"),
                "message": f"为 {item['title']} 留时间. 查找共同空档后选择时间, 再确认添加活动."}

    def activity_preview(self, payload, *, pair_note=""):
        group_token = payload.get("group_token")
        record = self._get_draft(group_token, "group_result")
        current = self.load()[1] if self.source_path().is_file() else None
        had_clocks = bool(record.get("group_clocks"))
        group = self._group_result(record, current, use_defaults=True)
        if "number" in payload:
            number = payload["number"]
            if type(number) is not int or not 1 <= number <= len(group.windows):
                raise ValueError("请从共同空闲列表选择有效的空档序号.")
            window = group.windows[number - 1]
            day, start, end = window.day, window.start, window.end
        else:
            day, start, end = (int(payload[key]) for key in ("day", "start", "end"))
            if payload.get("prefer_pair") is True and start == end:
                window = pick_grid_slot(group, day, start)
                start, end = window.start, window.end
                if start == end:
                    other = start + 1 if start % 2 else start - 1
                    pair_note = f"第 {other} 节有人忙, 已选择第 {start} 节."
        periods = str(start) if start == end else f"{start}-{end}"
        needs_clocks = start not in group.period_times or end not in group.period_times
        if needs_clocks:
            require_free_slot(group, day, start, end)
            target = group.monday + timedelta(days=day)
            time_label = ""
        else:
            begin, finish = available_slot(group, day, start, end)
            target = begin.date()
            time_label = f" {begin:%H:%M}-{finish:%H:%M}"
        label = f"{target:%Y-%m-%d} {DAYS[day]} 第 {periods} 节{time_label}"
        task_id = payload.get("todo_id")
        item = todo_list({"operation": "lookup", "id": task_id}) if task_id else None
        if item and item["done"]:
            raise ValueError("这条待办已完成, 需要安排时间时可先重新打开.")
        group_view = None
        clock_source = record.get("clock_source", "")
        if not had_clocks and record.get("group_clocks"):
            group_token = self._draft(record)
            group_view = self._group_view(group_token, group, clock_source)
        fields = {"day": day, "start": start, "end": end}
        open_schedule = payload.get("open_schedule") is True
        slot = self._draft({"type": "activity_slot", "group_token": group_token, "todo_id": task_id,
                            "pair_note": pair_note, "open_schedule": open_schedule, **fields})
        known = self._known_group_clocks(record, current) if record.get("group_clocks") else group.period_times
        can_edit = any(period not in known for period in range(start, end + 1))
        edit_clocks = payload.get("edit_clocks") is True and can_edit
        if open_schedule and not needs_clocks and not edit_clocks:
            schedule = self.planning.run({"operation": "start", "group_token": group_token, "day": day,
                                          "first": start, "last": end})
            selection_note = pair_note
            if payload.get("edit_clocks") is True:
                selection_note = "所选节次已有成员提供的作息, 已带入小组日程."
            return {**schedule, "group": group_view, "activity_token": slot, "selection_note": selection_note}
        options = group_clock_options(known, group.timezone, current) if can_edit else {}
        suffix = f" · {item['title']}" if item else ""
        hint = ("请在侧栏补齐钟点, 或用 /courseflow 确认组队作息 并附节次时间的 JSON 对象."
                if needs_clocks else "核对后可输入确认添加活动, 或制定小组日程.")
        return {"type": "activity", "token": slot, "group_token": group_token, "group": group_view,
                "fields": fields, "label": label, "date": target.isoformat(), "pair_note": pair_note, "task": item,
                "needs_clocks": needs_clocks, "can_edit_clocks": can_edit, "clock_source": clock_source,
                "open_schedule": open_schedule, "edit_clocks": edit_clocks,
                "clocks": _clock_fields(group.period_times), "known_clocks": _clock_fields(known),
                "clock_choices": {key: _clock_fields(values) for key, values in options.items()},
                "message": f"已选择 {label}{suffix}. {pair_note} {hint}".strip()}

    def activity_clocks(self, payload):
        slot = self._get_draft(payload.get("slot"), "activity_slot")
        record = self._get_draft(slot["group_token"], "group_result")
        current = self.load()[1] if self.source_path().is_file() else None
        group = self._group_result(record, current)
        known = self._known_group_clocks(record, current)
        clocks = payload.get("clocks")
        if payload.get("choice"):
            choice = group_clock_options(known, group.timezone, current).get(payload["choice"])
            if choice is None:
                raise ValueError("当前没有可采用的这套作息, 请按实际钟点填写.")
            clocks = _clock_fields(choice)
        if not isinstance(clocks, dict) or any(
            not re.fullmatch(r"(?:[1-9]|1[0-2])", str(period)) or not isinstance(span, str)
            or not re.fullmatch(r"(?:[0-9]{2}:[0-9]{2}-[0-9]{2}:[0-9]{2})?", span.strip())
            for period, span in clocks.items()
        ):
            raise ValueError("请按 08:00-08:45 的格式填写 1-12 节的作息.")
        known = _clock_fields(known)
        entered = {str(period): span.strip() for period, span in clocks.items() if span.strip()}
        if any(known.get(period, span) != span for period, span in entered.items()):
            raise ValueError("请保留成员已有的节次钟点, 只填写缺少的时间.")
        merged = {**_clock_fields(group.period_times), **entered}
        if str(slot["start"]) not in merged or str(slot["end"]) not in merged:
            raise ValueError("缺少所选时段的起止钟点, 请补齐对应节次.")
        timetable = service.configure_semester(Timetable(), "", group.monday, 1, merged, group.timezone)
        result = self._save_group_result({**record, "group_clocks": _clock_fields(timetable.period_times), "clock_source": "custom"})
        activity = self.activity_preview({**slot, "group_token": result["token"]}, pair_note=slot.get("pair_note", ""))
        return {**activity, "group": result}

    def activity(self, payload):
        if "slot" in payload:
            slot = self._get_draft(payload["slot"], "activity_slot")
            title = payload.get("title")
            if slot.get("todo_id"):
                item = todo_list({"operation": "lookup", "id": slot["todo_id"]})
                if item["done"]:
                    raise ValueError("这条待办已完成, 请重新核对.")
                title = title or item["title"]
            if not title or not str(title).strip():
                raise ValueError("请填写活动名称, 如确认添加活动 复习例题.")
            payload = {"room": payload.get("room", ""), "export_ics": payload.get("export_ics"), "title": title,
                       "token": slot["group_token"], **{key: slot[key] for key in ("day", "start", "end")}}
        token = payload.get("token")
        record = self._get_draft(token, "group_result")
        path = self._await_write(record)
        if not record["signature"]:
            raise ValueError("请先导入并保存我的课表, 再添加活动. 可先制定小组日程.")
        day, start, end = (int(payload[name]) for name in ("day", "start", "end"))
        tt, signature = service.load_timetable_snapshot(path)
        if signature != record["signature"]:
            raise ValueError("个人课表已更新, 请重新查询共同空闲.")
        date_row = self._group_result(record, tt)
        require_free_slot(date_row, day, start, end)
        title, room = str(payload.get("title", "")), str(payload.get("room", ""))
        updated, week = service.add_group_activity(tt, date_row.monday + timedelta(days=day), start, end, title, room,
                                                  group=date_row)
        files = []
        if payload.get("export_ics"):
            directory = self._out()
            meeting = write_meeting(date_row, day, start, end, title, directory / "组队活动.ics", room)
            files.append({"name": meeting.name, "id": f"{directory.name}/{meeting.name}"})
        service.save_timetable(updated, path, expected_signature=signature,
                               undo_path=self._undo_path(path), undo_label="添加组队活动")
        return {"type": "saved", "updated": True, "files": files, "message": "组队活动已保存, 并计入个人忙闲.",
                "week": week, "group_token": token}

    def point_grid(self, payload):
        cards = []
        basis = None
        token = payload.get("token")
        if token:
            record = self._get_draft(token, "group_result")
            cards = self._group_cards(record)
            week = record["week"]
        else:
            _, basis, _ = self.load()
            week = week_for(str(payload.get("text", "")), basis)
        directory = self._out()
        target = service.export_point_grid(directory / "忙闲点格页.html", basis, cards, week)
        return {"type": "saved", "files": [{"name": target.name, "id": f"{directory.name}/{target.name}"}],
                "message": "点格页已生成. 请发给成员填写并收回忙闲卡.", "return_group": bool(token)}


def exchange():
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("请求格式无效.")
        result = Harness().run(payload.pop("action"), payload)
        response = {"ok": True, "value": result}
    except SettingsRequired as exc:
        response = {"ok": False, "error": str(exc), "code": "ai_settings"}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        response = {"ok": False, "error": str(exc)}
    print(json.dumps(response, ensure_ascii=False, default=str))
    return 0


def write_demo_source(sample):
    demo = service.load_timetable(sample)
    demo = service.configure_semester(demo, demo.term, demo.semester_start, demo.weeks_total, SCHOOL_CLOCKS)
    save_source(demo, Path(os.environ["COURSEFLOW_SOURCE"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Copy the bundled sample into the demo profile.")
    parser.add_argument("--demo-source", type=Path)
    args = parser.parse_args()
    if args.demo or args.demo_source:
        write_demo_source(args.demo_source or Path(__file__).parent / "data" / "示例课表.yaml")
        return 0
    return exchange()


if __name__ == "__main__":
    raise SystemExit(main())
