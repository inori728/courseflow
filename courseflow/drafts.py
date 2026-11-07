"""Portable review drafts, kept separate from the user's saved timetable."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .model import DAYS, timetable_signature
from .notice import NoticeIntent
from .settings import atomic_text
from .vision import ImportDraft, draft_from_payload


def read_json(path) -> dict:
    path = Path(path)
    if path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("草稿文件过大.")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("无法读取 JSON 草稿, 请检查文件内容.") from exc
    if not isinstance(data, dict):
        raise ValueError("草稿最外层应为对象.")
    return data


def save_import_draft(draft: ImportDraft, path) -> Path:
    data = {"type": "courseflow-import", "version": 1, "origin": draft.origin, "notes": draft.notes,
            "courses": [{"name": c.name, "day": c.day_name, "periods": f"{c.start}-{c.end}", "weeks": c.weeks, "room": c.room} for c in draft.courses]}
    target = Path(path)
    atomic_text(target, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return target


def load_import_draft(path, total_weeks=16) -> ImportDraft:
    data = read_json(path)
    if data.get("type") != "courseflow-import" or data.get("version") != 1:
        raise ValueError("这不是支持的识图导入草稿.")
    draft = draft_from_payload(data, total_weeks, str(data.get("origin", "")))
    if not draft.courses:
        raise ValueError("草稿没有有效课程, 不能覆盖现有课表.")
    return draft


def intent_payload(intent: NoticeIntent) -> dict:
    value = asdict(intent)
    for key in ("source_day", "target_day"):
        value[key] = DAYS[value[key]] if value[key] is not None else None
    return value


def save_notice_draft(intent, tt, path) -> Path:
    data = {"type": "courseflow-notice", "version": 1, "timetable_signature": timetable_signature(tt),
            "intent": intent_payload(intent), "selection": [], "overrides": {}}
    target = Path(path)
    atomic_text(target, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return target


def load_notice_draft(path, tt):
    data = read_json(path)
    if data.get("type") != "courseflow-notice" or data.get("version") != 1:
        raise ValueError("这不是支持的通知调课草稿.")
    if data.get("timetable_signature") != timetable_signature(tt):
        raise ValueError("草稿生成后课表已有变化, 请重新解析通知.")
    if not isinstance(data.get("intent"), dict):
        raise ValueError("草稿缺少 intent 对象.")
    intent = NoticeIntent.from_payload(data["intent"], tt.weeks_total)
    selection = data.get("selection", [])
    overrides = data.get("overrides", {})
    if not isinstance(selection, list) or not isinstance(overrides, dict):
        raise ValueError("selection 应为序号列表, overrides 应为对象.")
    return intent, selection, overrides
