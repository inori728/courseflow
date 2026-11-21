"""Independent local task list for the Harness companion."""
from __future__ import annotations

from datetime import date, timedelta
import json
import re
from uuid import uuid4

from .service import _timetable_lock
from .settings import atomic_text, settings_dir


def _read(path):
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    if not isinstance(items, list) or any(not isinstance(item, dict) or not isinstance(item.get("id"), str)
                                          or not isinstance(item.get("title"), str) for item in items):
        raise ValueError("待办文件格式有误, 请先核对本地文件.")
    return items


def _matches(items, fields):
    token = fields.get("id")
    if token:
        matches = [item for item in items if item["id"] == token]
    else:
        needle = str(fields.get("title", "")).strip().casefold()
        if not needle:
            raise ValueError("请填写待办名称.")
        matches = [item for item in items if item["title"].casefold() == needle]
        if not matches:
            matches = [item for item in items if needle in item["title"].casefold()]
    return matches


def _find(items, fields):
    matches = _matches(items, fields)
    if len(matches) != 1:
        raise ValueError("找不到这条待办." if not matches else "有多条同名或相似待办, 请在侧栏选择.")
    return matches[0]


def todo_matches(title):
    return _matches(_read(settings_dir() / "todos.json"), {"title": title})


def todo_list(fields):
    path = settings_dir() / "todos.json"
    operation = fields.get("operation", "list")
    if operation == "list":
        return {"type": "todos", "items": _read(path)}
    if operation == "lookup":
        return _find(_read(path), fields)
    with _timetable_lock(path):
        items = _read(path)
        if operation == "add":
            title = str(fields.get("title", "")).strip()
            course = str(fields.get("course", "")).strip()
            due = str(fields.get("due", "")).strip()
            if not 1 <= len(title) <= 120 or len(course) > 120:
                raise ValueError("待办名称必填, 名称和关联课程最多 120 字.")
            if due:
                due = date.fromisoformat(due).isoformat()
            items.append({"id": uuid4().hex, "title": title, "course": course, "due": due, "done": False})
            message = "已添加待办."
        elif operation == "remove":
            items.remove(_find(items, fields))
            message = "已删除待办."
        elif operation == "complete":
            if not isinstance(fields.get("done"), bool):
                raise ValueError("请选择有效的完成状态.")
            _find(items, fields)["done"] = fields["done"]
            message = "待办状态已更新."
        else:
            raise ValueError("未知的待办操作.")
        atomic_text(path, json.dumps(items, ensure_ascii=False, indent=2) + "\n")
    return {"type": "todos", "items": items, "message": message}


def todo_command(text, today):
    matched = re.fullmatch(r"(添加|删除|查看|完成|取消完成|重开|重新打开)(?:待办|待做任务)(?:\s*(.+))?", text, re.S)
    if not matched:
        return None
    command, title = matched[1], (matched[2] or "").strip()
    if command == "查看":
        return {}
    if command == "删除":
        return {"operation": "remove", "title": title}
    if command in {"完成", "取消完成", "重开", "重新打开"}:
        return {"operation": "complete", "title": title, "done": command == "完成"}
    due = ""
    relative = re.match(r"^(今天|明天|后天|(?:本|下)?周[一二三四五六日天]|[0-9]{4}-[0-9]{2}-[0-9]{2})前\s*(.*)$", title, re.S)
    if relative:
        token, title = relative.groups()
        if "周" in token:
            weekday = "一二三四五六日".index(token[-1].replace("天", "日"))
            offset = weekday - today.weekday()
            if token.startswith("下") or (not token.startswith("本") and offset < 0):
                offset += 7
            due = (today + timedelta(days=offset)).isoformat()
        elif token in {"今天", "明天", "后天"}:
            due = (today + timedelta(days=("今天", "明天", "后天").index(token))).isoformat()
        else:
            due = token
    title, _, course = title.partition(" 课程:") if " 课程:" in title else title.partition(" 课程\uff1a")
    return {"operation": "add", "title": title, "due": due, "course": course}
