"""Harness planning actions. Group and timetable data remain local."""
from __future__ import annotations

import base64
from datetime import date, datetime, time, timedelta
from io import BytesIO
import json
import re

from .group import common_free
from .planning import (_clock, member_labels, require_free, request_conditions, schedule_draft, schedule_options,
                       selected_slot, suggest_agenda)
from .schedule import resolve_timetable
from .schedule_card import CARD_STYLES, render_schedule_card, write_schedule_card
from .semester import SemesterCalendar, _tzinfo


def schedule_command(text):
    if text in {"日程", "查看日程", "打开日程"}:
        return "current"
    if re.match(r"^(?:(?:请|帮我)\s*)?(?:约|安排.*(?:小组|会议|日程))", text):
        return "find"
    if re.match(r"^(?:确认缩短并?)?选(?:择)?方案\s*[A-Ea-e]", text):
        return "choose"
    if re.match(r"^(?:地点(?:定在|改到|设为)|集合地点(?:定在|改到|设为))", text):
        return "place"
    if re.fullmatch(r"(?:确认应用|应用)(?:本次)?日程(?:修改|调整)", text):
        return "apply"
    if re.fullmatch(r"撤销(?:小组)?日程(?:修改|更改)?", text):
        return "undo"
    if text in {"取消日程修改", "放弃日程修改"}:
        return "discard"
    if re.match(r"^预览(?:小组)?日程卡", text):
        return "preview"
    if re.match(r"^导出(?:小组)?日程卡", text):
        return "export"
    if re.match(r"^设置日程\s+", text):
        return "fields"
    if re.match(r"^编辑日程(?:修改)?\s+", text):
        return "json_edit"
    if re.match(r"^添加(?:现场议程|议程|会前分工|分工)\s+", text):
        return "append"
    if re.match(r"^(?:给日程|为日程|拟议程|生成议程)", text):
        return "suggest"
    if re.match(r"^(?:改日程|重排日程|(?:把|将).*(?:日程|议程).*(?:换到|改到|调到|改为|改成|调整))", text):
        return "revise"
    return None


class HarnessPlanning:
    def __init__(self, backend):
        self.backend = backend

    def _result(self, record, when):
        cards = self._cards(record)
        week = (when - cards[0].semester_start).days // 7 + 1
        return common_free(cards, week, 1)

    def _cards(self, record):
        cards = self.backend._group_cards(record["group"])
        if "participants" in record:
            cards = [card for card in cards if card.name in record["participants"]]
        if not cards:
            raise ValueError("请先添加参与成员的课表或忙闲卡.")
        return cards

    def _validate(self, record, fields, required=False):
        result = self._result(record, date.fromisoformat(fields["date"]))
        require_free(result, fields)
        labels = member_labels(fields.get("members", result.names), result.names)
        return schedule_draft(fields, labels, require_title=required)

    def _new(self, record):
        return self._view(record, self.backend._draft(record))

    @staticmethod
    def _view(record, token):
        if record["type"] == "schedule_options":
            return {"type": "schedule_options", "token": token, "group_token": record["group_token"],
                    "options": record["options"], "warnings": record["warnings"], "title": record["fields"]["title"],
                    "minutes": record["minutes"], "preferred_date": record["preferred_date"]}
        return {"type": "schedule", "token": token, "group_token": record["group_token"], "draft": record["draft"],
                "review": record.get("review"), "has_undo": bool(record.get("previous"))}

    def _start(self, fields):
        group_token = fields["group_token"]
        group = self.backend._get_draft(group_token, "group_result")
        result = self.backend._group_result(group)
        day, first, last = (int(fields[key]) for key in ("day", "first", "last"))
        slot = selected_slot(result, day, first, last)
        draft = schedule_draft(slot, result.names)
        return self._new({"type": "schedule", "group_token": group_token, "group": group, "draft": draft})

    def _deadline(self, requirements, default):
        if requirements.get("before_class_date"):
            when = date.fromisoformat(requirements["before_class_date"])
            _, tt, _ = self.backend.load()
            calendar = SemesterCalendar.from_timetable(tt)
            week = (when - calendar.start).days // 7 + 1
            starts = [tt.period_times[occ.start][0] for occ in resolve_timetable(tt, tt.weeks_total)
                      if occ.week == week and occ.day == when.weekday() and occ.start in tt.period_times
                      and occ.course.kind != "activity"]
            if not starts:
                raise ValueError("没有查到当天课程的开始钟点. 请在约事指令中给出明确截止时间.")
            return datetime.combine(when, min(starts))
        if requirements.get("deadline"):
            value = datetime.fromisoformat(requirements["deadline"])
            if value.tzinfo is not None:
                raise ValueError("请用课表时区的本地钟点填写截止时间.")
            return value
        return default

    def _find(self, fields):
        group_token = fields.get("group_token")
        if not group_token:
            raise ValueError("请先在组队页查出成员的共同空闲, 或随约事指令附上成员课表或忙闲卡.")
        text = str(fields.get("text", "")).strip()
        if not 1 <= len(text) <= 2000:
            raise ValueError("请填写活动, 参与人, 时长和时间偏好, 最多 2000 字.")
        group = self.backend._get_draft(group_token, "group_result")
        record = {"type": "schedule_options", "group_token": group_token, "group": group}
        cards = self._cards(record)
        now = datetime.now(_tzinfo(cards[0].timezone)[0]).replace(tzinfo=None)
        earliest = now.replace(second=0, microsecond=0) + timedelta(minutes=bool(now.second or now.microsecond))
        requirements = request_conditions(self.backend.require_vision(), text, now.date(), cards)
        if requirements.get("question"):
            raise ValueError(str(requirements["question"])[:300])
        minutes = requirements.get("minutes")
        if type(minutes) is not int or not 1 <= minutes <= 1440:
            raise ValueError("请明确活动所需时长, 例如连续 60 分钟.")
        names = requirements.get("participants") or []
        if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
            raise ValueError("请核对参与人.")
        if names:
            known = {card.name.casefold(): card.name for card in cards}
            if any(name.strip().casefold() not in known for name in names):
                raise ValueError("约事指令中的成员未全部出现在组队资料中. 请先补充或核对成员.")
            record["participants"] = list(dict.fromkeys(known[name.strip().casefold()] for name in names))
            cards = self._cards(record)
        if requirements.get("participant_count") not in (None, len(cards)):
            raise ValueError(f"当前有 {len(cards)} 位已选成员. 请核对约事人数, 或提供其他成员的忙闲资料.")
        preferred_date = date.fromisoformat(requirements["preferred_date"]) if requirements.get("preferred_date") else None
        preferred_start = _clock(requirements["preferred_start"]) if requirements.get("preferred_start") else time.min
        preferred_end = _clock(requirements["preferred_end"]) if requirements.get("preferred_end") else time.max
        if preferred_start >= preferred_end:
            raise ValueError("请明确同一天内的偏好时间范围.")
        default_deadline = datetime.combine(max(now.date() + timedelta(days=13), preferred_date or now.date()), time(23, 59))
        deadline = self._deadline(requirements, default_deadline)
        if deadline <= earliest:
            raise ValueError("截止时间已过. 请指定之后的时间.")

        results = []
        missing = False
        first = cards[0]
        begin_week = max(1, (earliest.date() - first.semester_start).days // 7 + 1)
        end_week = min(104, (deadline.date() - first.semester_start).days // 7 + 1)
        for week in range(begin_week, end_week + 1):
            monday = first.semester_start + timedelta(weeks=week - 1)
            if any((monday - card.semester_start).days // 7 + 1 not in card.busy for card in cards):
                missing = True
                continue
            results.append(common_free(cards, week, 1))
        warnings = list(dict.fromkeys(warning for result in results for warning in result.warnings))
        if missing:
            warnings.append("有些周缺少成员忙闲资料, 已略过这些周.")
        if not any(result.period_times for result in results):
            warnings.append("查询范围缺少可用的成员资料或节次钟点. 请补齐后重试.")
        options = schedule_options(results, minutes, earliest, deadline, (preferred_date, preferred_start, preferred_end))
        values = {key: requirements.get(key) or "" for key in ("title", "room", "notes")}
        if not isinstance(values["title"], str) or not values["title"].strip():
            raise ValueError("请在指令中明确要安排的活动.")
        record.update(options=options, fields=values, minutes=minutes, warnings=warnings,
                      preferred_date=preferred_date.isoformat() if preferred_date else "")
        return self._new(record)

    def _choose(self, fields):
        token = fields.get("token")
        record = self.backend._get_draft(token, "schedule_options")
        index = int(fields["index"])
        if not 0 <= index < len(record["options"]):
            raise ValueError("请选择当前列表中的方案.")
        option = record["options"][index]
        if option["kind"] == "shorter" and fields.get("confirm_shorter") is not True:
            return {**self._view(record, token), "message": "该方案会缩短活动. 请在侧栏确认接受缩短后使用."}
        values = {**option, **record["fields"]}
        if "room" in fields:
            values["room"] = fields["room"]
        draft = self._validate(record, values, required=True)
        return self._new({**record, "type": "schedule", "draft": draft})

    def run(self, fields):
        operation = fields.get("operation")
        if operation == "start":
            return self._start(fields)
        if operation == "find":
            return self._find(fields)
        if operation == "choose":
            return self._choose(fields)

        token = fields.get("token")
        if operation == "current":
            if not token:
                return {"type": "schedule_empty"}
            record = self.backend._get_draft(token, ("schedule", "schedule_options"))
            return self._view(record, token)
        record = self.backend._get_draft(token, "schedule")
        draft = record["draft"]
        edits = fields.get("draft", {})
        if operation in {"suggest", "revise"}:
            draft = self._validate(record, {**draft, **edits})
            text = str(fields.get("text", "")).strip()
            if not 1 <= len(text) <= 2000:
                raise ValueError("请填写日程目标或修改要求, 最多 2000 字.")
            today = datetime.now(_tzinfo(self._cards(record)[0].timezone)[0]).date()
            review = suggest_agenda(self.backend.require_vision(), draft, text, revise=operation == "revise", today=today,
                                    check_slot=lambda target: self._validate(record, target))
            self._validate(record, review["draft"], required=True)
            return self._new({**record, "draft": draft, "review": review})
        if operation == "apply":
            if not record.get("review"):
                raise ValueError("请先生成并核对日程修改.")
            draft = self._validate(record, {**record["review"]["draft"], **edits}, required=True)
            return self._new({**record, "draft": draft, "previous": record["draft"], "review": None})
        if operation == "discard":
            return self._new({**record, "review": None})
        if operation == "undo":
            if not record.get("previous"):
                raise ValueError("当前没有可撤销的日程修改.")
            return self._new({**record, "draft": record["previous"], "previous": None, "review": None})
        if operation in {"save", "preview", "export"}:
            if record.get("review"):
                raise ValueError("请先应用或取消正在对照的日程修改.")
            draft = self._validate(record, {**draft, **edits}, required=operation != "save")
            view = self._new({**record, "draft": draft})
            if operation == "save":
                return {**view, "message": "日程草稿已保存."}
            style = fields.get("style", "green")
            if style not in CARD_STYLES:
                raise ValueError("请选择有效的日程卡样式.")
            if operation == "preview":
                image = render_schedule_card(draft, style)
                image.thumbnail((540, 1400))
                output = BytesIO()
                image.save(output, "PNG")
                return {**view, "preview": base64.b64encode(output.getvalue()).decode("ascii"), "style": style}
            directory = self.backend._out()
            target = write_schedule_card(draft, style, directory / f"小组日程安排-{CARD_STYLES[style]}.png")
            return {**view, "files": [{"name": target.name, "id": f"{directory.name}/{target.name}"}],
                    "message": "日程卡已导出."}
        raise ValueError("未知的小组日程操作.")

    def command(self, operation, payload, text):
        token = payload.get("schedule_token")
        fields = {"operation": operation, "token": token, "text": text}
        if operation == "find":
            if payload.get("files"):
                return self.backend.run("group_prepare", {**payload, "plan_request": text})
            fields["group_token"] = payload.get("group_token")
        elif operation == "choose":
            matched = re.match(r"^(?:确认缩短并?)?选(?:择)?方案\s*([A-Ea-e])", text)
            fields["index"] = ord(matched[1].upper()) - ord("A")
            fields["confirm_shorter"] = text.startswith("确认缩短")
            rest = text[matched.end():].lstrip(" ,\uff0c")
            place = re.match(r"地点(?:定在|改到|设为)\s*(.+)", rest)
            if place:
                fields["room"] = place[1]
        elif operation == "place":
            fields.update(operation="save", draft={"room": re.sub(r"^(?:集合)?地点(?:定在|改到|设为)\s*", "", text)})
        elif operation in {"export", "preview"}:
            fields["style"] = "simple" if "简洁" in text else "green"
        elif operation == "fields":
            names = {"事项": "title", "地点": "room", "日期": "date", "开始": "start", "结束": "end", "说明": "notes"}
            updates = {}
            for entry in re.split(r"[|\uff5c]", text.removeprefix("设置日程").strip()):
                pair = re.split(r"[:\uff1a]", entry, maxsplit=1)
                if len(pair) != 2 or pair[0].strip() not in names:
                    raise ValueError("请按字段填写, 如设置日程 事项:小组讨论 | 地点:研讨室.")
                updates[names[pair[0].strip()]] = pair[1].strip()
            fields.update(operation="save", draft=updates)
        elif operation == "json_edit":
            leader, data = text.split(maxsplit=1)
            try:
                draft = json.loads(data)
            except (ValueError, TypeError) as exc:
                raise ValueError("请提供日程字段的 JSON 对象.") from exc
            if not isinstance(draft, dict) or set(draft) - {"title", "room", "notes", "date", "start", "end", "members", "agenda", "prep"}:
                raise ValueError("请核对日程 JSON 字段, 可看使用说明.")
            fields.update(operation="apply" if leader.strip() == "编辑日程修改" else "save", draft=draft)
        elif operation == "append":
            draft = self.backend._get_draft(token, "schedule")["draft"]
            entry = re.fullmatch(r"添加(?:现场)?议程\s+([0-9]{1,4})\s*(?:分钟)?\s*\|\s*(.+)", text)
            if entry:
                updates = {"agenda": draft["agenda"] + [{"minutes": int(entry[1]), "title": entry[2]}]}
            else:
                entry = re.fullmatch(r"添加(?:会前)?分工\s+([^|]+)\|\s*(.+)", text)
                if not entry:
                    raise ValueError("请用 添加议程 10 | 复盘错题 或 添加分工 甲/乙 | 整理资料.")
                owners = [name.strip() for name in re.split(r"[/,\uff0c\u3001]", entry[1]) if name.strip()]
                updates = {"prep": draft["prep"] + [{"owners": owners, "title": entry[2]}]}
            fields.update(operation="save", draft=updates)
        return self.run(fields)
