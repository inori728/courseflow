"""Minute-level planning on top of the shared group availability grid."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
import json
import re

from .ai import AIClient
from .group import available_slot


# The school preset has 10- and 20-minute transitions. A longer gap has no
# coverage in a busy card, even when both neighboring periods are free.
MAX_TRANSITION = timedelta(minutes=20)


def continuous_slots(result, day, first=1, last=12):
    """Return local clock intervals backed by free cells and known clocks."""
    when = result.monday + timedelta(days=day)
    windows = []
    last_period = None
    for period in range(first, last + 1):
        clocks = result.period_times.get(period)
        if not clocks or result.counts[day * 12 + period - 1]:
            continue
        start, end = (datetime.combine(when, clock) for clock in clocks)
        if last_period == period - 1 and timedelta(0) <= start - windows[-1][3] <= MAX_TRANSITION:
            windows[-1] = (windows[-1][0], period, windows[-1][2], end)
        else:
            windows.append((period, period, start, end))
        last_period = period
    return windows


def clock_windows(result, day):
    return [(start, end) for _, _, start, end in continuous_slots(result, day)]


def slot_fields(start, end):
    return {"date": start.date().isoformat(), "start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")}


def selected_slot(result, day, first, last):
    start, end = (item.replace(tzinfo=None) for item in available_slot(result, day, first, last))
    for window_start, window_end in clock_windows(result, day):
        if window_start <= start < window_end:
            return slot_fields(start, min(end, window_end))
    raise ValueError("所选时段缺少可核对的节次钟点.")


def _clock(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{2}:[0-9]{2}", value):
        raise ValueError("请按 HH:MM 填写钟点.")
    return time.fromisoformat(value)


def clock_span(fields):
    when = date.fromisoformat(str(fields.get("date", "")))
    start = datetime.combine(when, _clock(fields.get("start")))
    end = datetime.combine(when, _clock(fields.get("end")))
    if end <= start:
        raise ValueError("结束时间必须晚于同一天的开始时间.")
    return start, end


def require_free(result, fields):
    start, end = clock_span(fields)
    day = (start.date() - result.monday).days
    if not 0 <= day < 7 or not any(a <= start < end <= b for a, b in clock_windows(result, day)):
        raise ValueError("这个时段不在可核对的全员空档内. 请检查日期, 钟点和成员资料.")
    return int((end - start).total_seconds() // 60)


def _text(value, limit, label, required=False):
    if not isinstance(value, str):
        raise ValueError(f"请填写有效的{label}.")
    value = value.strip()
    if len(value) > limit or (required and not value):
        raise ValueError(f"请填写{label}, 最多 {limit} 字.")
    return value


def _list(value, limit, label):
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"{label}最多 {limit} 项.")
    return value


def schedule_draft(fields, members, *, require_title=False):
    start, end = clock_span(fields)
    people = [_text(item, 80, "成员名称", True) for item in _list(list(members), 100, "成员")]
    agenda = []
    for row in _list(fields.get("agenda", []), 12, "现场议程"):
        minutes = row.get("minutes") if isinstance(row, dict) else None
        if type(minutes) is not int or not 1 <= minutes <= 1440:
            raise ValueError("每段现场议程须填写正整数分钟数.")
        agenda.append({"minutes": minutes, "title": _text(row.get("title", ""), 120, "议程内容", True)})
    if sum(row["minutes"] for row in agenda) * 60 > (end - start).total_seconds():
        raise ValueError("现场议程超过所选时长. 请缩短议程或更换时段.")
    prep = []
    for row in _list(fields.get("prep", []), 12, "会前分工"):
        if not isinstance(row, dict):
            raise ValueError("请核对会前分工.")
        owners = [_text(item, 80, "负责人", True) for item in _list(row.get("owners", []), 100, "负责人")]
        if any(item not in people and item not in {"全员", "待分配"} for item in owners):
            raise ValueError("负责人须来自当前成员或其代号, 也可填写全员或待分配.")
        if len(set(owners)) > 1 and set(owners) & {"全员", "待分配"}:
            raise ValueError("全员和待分配须单独使用.")
        prep.append({"title": _text(row.get("title", ""), 120, "准备事项", True),
                     "owners": list(dict.fromkeys(owners)) or ["待分配"]})
    return {**slot_fields(start, end), "title": _text(fields.get("title", ""), 120, "事项", require_title),
            "room": _text(fields.get("room", ""), 120, "地点"), "notes": _text(fields.get("notes", ""), 240, "说明"),
            "agenda": agenda, "prep": prep, "members": people}


def member_labels(values, names):
    labels = [_text(label, 80, "成员代号", True) for label in _list(values, len(names), "成员代号")]
    if len(labels) != len(names) or len(set(labels)) != len(labels) or {"全员", "待分配"}.intersection(labels):
        raise ValueError("请为每位成员填写一个不同的名称或代号.")
    return labels


def _overlap(start, end, left, right):
    start, end = max(start, left), min(end, right)
    return (start, end) if start < end else None


def schedule_options(results, minutes, earliest, deadline, preferred):
    duration = timedelta(minutes=minutes)
    best, other, shorter = [], [], []
    for result in results:
        for day in range(7):
            when = result.monday + timedelta(days=day)
            preferred_span = (datetime.combine(when, preferred[1]), datetime.combine(when, preferred[2]))
            for a, b in clock_windows(result, day):
                window = _overlap(a, b, earliest, deadline)
                if not window:
                    continue
                start, end = window
                match = _overlap(start, end, *preferred_span) if preferred[0] in (None, when) else None
                if match and match[1] - match[0] >= duration:
                    best.append((match[0], match[0] + duration))
                elif end - start >= duration:
                    other.append((start, start + duration))
                if match and match[1] - match[0] < duration:
                    shorter.append(match)
    options = [{**slot_fields(a, b), "kind": "preferred"} for a, b in best[:4]]
    if preferred[0] is not None:
        other.sort(key=lambda pair: (pair[0].date() == preferred[0], pair[0]))
    options.extend({**slot_fields(a, b), "kind": "alternative"} for a, b in other[:max(0, 4 - len(options))])
    if not best and shorter:
        a, b = max(shorter, key=lambda pair: pair[1] - pair[0])
        options.append({**slot_fields(a, b), "kind": "shorter"})
    return options


def request_conditions(config, phrase, today, members, *, transport=None):
    prompt = (
        'Extract a group scheduling request in the supplied local calendar. Return JSON only: '
        '{"title":"", "room":"", "notes":"", "minutes":60, "participant_count":null, "participants":[], '
        '"preferred_date":null, "preferred_start":null, "preferred_end":null, "deadline":null, '
        '"before_class_date":null, "question":""}. Dates YYYY-MM-DD, clocks HH:MM, deadline YYYY-MM-DDTHH:MM. '
        'A date-only deadline means 23:59. For before classes on a date, use before_class_date instead of guessing '
        'a time. Resolve relative days from today, including week boundaries. Use null for unspecified values. '
        'If necessary details like duration are ambiguous, ask a short question in the user language. '
        'Use the user language for title and notes. Extract explicit participant names or a count, never invent names.'
    )
    data = {"today": today.isoformat(), "member_count": len(members), "request": phrase}
    return AIClient(config, transport).json(prompt, json.dumps(data, ensure_ascii=False))


def suggest_agenda(config, draft, request, *, revise=False, check_slot=None, today=None, transport=None):
    client = AIClient(config, transport)
    today = (today or date.today()).isoformat()
    target = draft
    if revise:
        conditions = client.json(
            'Extract only requested changes to date, start, end, title, room, or notes. Return a JSON object, '
            'using YYYY-MM-DD and HH:MM in the supplied local calendar. Omit unchanged fields. For a requested '
            'duration without a new end time, calculate the end from the selected start. If a requested move is '
            'ambiguous, return a short question in the user language in the question field. Do not draft an agenda yet.',
            json.dumps({"current": {key: draft[key] for key in ("date", "start", "end", "title", "room", "notes")},
                        "request": request, "today": today}, ensure_ascii=False),
        )
        if conditions.get("question"):
            raise ValueError(str(conditions["question"])[:300])
        changes = {key: conditions[key] for key in ("date", "start", "end", "title", "room", "notes") if key in conditions}
        target = schedule_draft({**draft, **changes, "agenda": [], "prep": []}, draft["members"])
        if check_slot is not None:
            check_slot(target)
    prompt = (
        'Prepare a reviewable group schedule in the user language. Return one JSON object with these fields. '
        '{"title":"","room":"","notes":"","agenda":[{"minutes":10,"title":""}],'
        '"prep":[{"title":"","owners":[]}],"summary":""}. '
        'Keep the target date, start, end and members fixed. Fill only blank title, room and notes fields. '
        'Derive a short title from what the user wants to accomplish. For a blank room, copy a meeting venue '
        'exactly as written if the request explicitly gives one. Otherwise return an empty room. '
        'Use notes for concrete goals or requirements in the request, or leave them empty. '
        'Keep total agenda minutes within the verified target window. Use only supplied member names or aliases, or '
        'use the Chinese values \u5168\u5458 and \u5f85\u5206\u914d. Owners may include multiple members. '
        'Do not invent commitments or modify any outside data. Fill summary with material changes, especially shortened agenda '
        'items or work moved into prep. Preserve explicit time allocations.'
    )
    result = client.json(prompt, json.dumps({
        "current": draft, "target": target, "request": request, "revise": revise, "today": today,
    }, ensure_ascii=False))
    if "agenda" not in result or "prep" not in result:
        raise ValueError("AI 返回缺少议程或分工, 请重试或手动填写.")
    title = target["title"] or _text(result.get("title") or "", 120, "事项")
    if not title:
        raise ValueError("AI 未能生成事项, 请在描述中补充小组要做什么后重试.")
    room = target["room"]
    if not room:
        proposed_room = _text(result.get("room") or "", 120, "地点")
        if proposed_room in request:
            room = proposed_room
    updated = schedule_draft({
        **target, "title": title, "room": room, "notes": target["notes"] or result.get("notes") or "",
        "agenda": result["agenda"], "prep": result["prep"],
    }, draft["members"], require_title=True)
    summary = _text(result.get("summary", ""), 500, "改动摘要")
    return {"draft": updated, "request": request, "summary": summary}
