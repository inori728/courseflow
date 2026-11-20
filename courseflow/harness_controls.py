"""Command entry points for the same local operations used by the Harness sidebar."""
from __future__ import annotations

import json
import re

from .backgrounds import BACKGROUNDS, normalize
from .harness_commands import _DAY, _NUM, _WEEK, formats_for, group_minimum, period_span, week_for
from .model import parse_day
from .weeks import _number


HELP = "\n".join((
    "CourseFlow 命令示例 (均在指令前加 /courseflow):",
    "课表: 查第7周的课 / 上一周 / 周课表网格 / 下次数据结构在哪上 / 刷新课表",
    "设置: 设置当前周次 7 / 确认周次 / 打开 AI 接口设置 / 自检 AI 接口",
    "导入与调课: 导入课表 (附文件) / 预览 / 选课次 1 / 确认导入 / 确认调课 / 撤销上一步",
    "导出: 导出手机壁纸 背景:海边教室 / 预览 / 确认导出 / 导出点格页",
    "待办: 添加待办 周五前交实验报告 / 完成待办 交实验报告 / 给待办 交实验报告 留出时间",
    "组队: 查第7周共同空闲 (附成员资料) / 确认组队 / 选空档 1 / 确认添加活动",
    "连堂: 选空档 周三第3小节 优先连堂 / 选空档 周三第2大节",
    "打开日程: 选空档 周三第2大节 并打开日程",
    "调整默认作息: 选空档后可用 确认组队作息 我的课表 / 确认组队作息 预设, 或附节次时间的 JSON 对象",
    "日程: 制定小组日程 / 查看日程 / 设置日程 事项:小组讨论 / 预览日程卡 / 导出日程卡",
))


def _view(name, message, *, refresh=False):
    return {"type": "open_view", "view": name, "message": message, "refresh": refresh}


def _object(text):
    try:
        result = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ValueError("请在命令后提供 JSON 对象, 可从使用说明查看示例.") from exc
    if not isinstance(result, dict):
        raise ValueError("请提供 JSON 对象.")
    return result


def run_control(app, payload, text):
    text = text.strip().rstrip(".\u3002")
    context = payload.get("workbench") or {}
    if text in {"帮助", "命令", "命令帮助"}:
        return {"type": "command_help", "message": HELP}
    if text in {"课表", "查看课表", "刷新课表"}:
        return _view("agenda", "已刷新课表.", refresh=True)
    if text in {"组队", "打开组队"} and not payload.get("files"):
        return _view("group", "请添加课表或忙闲卡来查找共同空闲.")
    if text in {"待办", "打开待办"}:
        return app.run("todos", {})
    if text in {"AI 接口设置", "AI接口设置", "打开 AI 接口设置", "打开AI接口设置", "配置AI接口", "配置 AI 接口"}:
        return {"type": "settings", "message": "已打开 AI 接口设置. 在侧栏填写或更新 Key."}
    if re.fullmatch(r"(?:自检|验证)\s*AI\s*接口", text, re.I):
        return app.ai_self_check()

    week_setting = re.fullmatch(rf"设置当前周次(?:\s*(?:第\s*)?({_NUM})\s*周?)?", text)
    if week_setting:
        week = _number(week_setting[1]) if week_setting[1] else None
        return app.semester_week({"suggested_week": week})
    confirm_week = re.fullmatch(rf"(?:确认周次|保存周次)(?:\s*(?:第\s*)?({_NUM})\s*周?)?", text)
    if confirm_week:
        week = _number(confirm_week[1]) if confirm_week[1] else context.get("suggested_week")
        return app.save_semester_week({"token": context.get("semester"), "week": week})
    if text in {"撤销上一步", "撤销课表修改"}:
        status = app.status({})
        if not status.get("undo"):
            raise ValueError("当前课表没有可撤销的改动.")
        return app.undo({"token": status["undo"]["token"]})

    view = re.fullmatch(r"(?:(?:切换到|切换|查看)\s*)?(按日卡片|周课表网格)", text)
    if view or text in {"上一周", "下一周"}:
        _, tt, _ = app.load()
        week = context.get("agenda_week")
        if week is None:
            try:
                week = week_for("", tt)
            except ValueError:
                week = 1
        if not view:
            week += 1 if text == "下一周" else -1
        if not 1 <= week <= tt.weeks_total:
            raise ValueError("已经到学期边界, 请选择学期内的周次.")
        result = app.week_agenda(tt, week)
        if view:
            result["view_mode"] = "week" if view[1] == "周课表网格" else "day"
        return result

    if text == "导入课表" and not payload.get("files"):
        return _view("import", "请在命令中附上课表文件或在侧栏选择附件.")
    if re.match(r"^导入(?:我的|当前)?课表", text) and payload.get("files"):
        return app.run("prepare", {**payload, "mode": "import"})
    if text in {"预览", "预览导入", "预览调课", "预览导出"}:
        return app.command_preview(context.get("prepared"), {})
    edit = re.fullmatch(r"编辑课表\s+(\{.*\})", text, re.S)
    if edit:
        return app.command_preview(context.get("prepared"), _object(edit[1]))
    selection = re.fullmatch(r"选(?:择)?课次\s*(全部|[0-9,\uff0c\u3001 ]+)", text)
    if selection:
        candidates = context.get("candidates", [])
        indices = list(range(1, len(candidates) + 1)) if selection[1] == "全部" else [int(n) for n in re.findall(r"[0-9]+", selection[1])]
        if not indices or any(not 1 <= n <= len(candidates) for n in indices):
            raise ValueError("请用预览中显示的课次序号, 或输入选课次 全部.")
        return app.command_preview(context.get("prepared"), {"selected": [candidates[n - 1] for n in dict.fromkeys(indices)]})
    if text in {"确认导入", "确认调课", "确认导出", "确认生成"}:
        token = context.get("confirmation")
        draft = app._get_draft(token, "confirmed")
        expected = "调课" if draft["overwrite"] and draft["change"] else "导入" if draft["overwrite"] else "导出"
        if text[2:] != expected and not (text == "确认生成" and expected == "导出"):
            raise ValueError(f"这份预览对应{expected}, 请用确认{expected}.")
        return app.commit({"token": token})

    group_token = payload.get("group_token")
    if text in {"刷新组队", "刷新空闲", "查看组队结果"}:
        return app.group_refresh({"token": group_token})
    group_edit = re.fullmatch(r"编辑组队\s+(\{.*\})", text, re.S)
    if group_edit or re.match(r"^确认组队(?:\s|第|$)", text):
        fields = _object(group_edit[1]) if group_edit else {}
        if not group_edit:
            specified = re.search(_WEEK, text)
            if specified:
                fields["week"] = _number(specified[1])
            if "连续" in text or "至少" in text:
                fields["minimum"], fields["minutes"] = group_minimum(text)
        return app.confirm_group(context.get("group_prepare"), fields)
    if "点格页" in text or "点格链接" in text:
        return app.point_grid({"token": group_token if not re.search(_WEEK, text) else None, "text": text})

    reserve = re.fullmatch(r"(?:给|为)(?:待办|待做任务)\s*(.+?)\s*留(?:出)?时间", text)
    if reserve:
        return app.reserve_todo({"title": reserve[1], "group_token": group_token})
    if text == "取消待办安排":
        return {"type": "todo_reserve", "item": None, "group_token": group_token, "message": "已取消选中的待办安排."}
    slot = re.fullmatch(r"选(?:择)?空档\s*(.+)", text)
    if slot:
        chosen = slot[1]
        fields = {"group_token": group_token, "todo_id": context.get("todo_id")}
        if re.fullmatch(_NUM, chosen):
            fields["number"] = _number(chosen)
        else:
            weekday, periods = re.search(_DAY, chosen), period_span(chosen)
            if not weekday or not periods:
                raise ValueError("请写空档序号, 或写星期和节次, 如选空档 周二 3-4节.")
            first, _, last = periods.partition("-")
            fields.update(day=parse_day(weekday[0].replace("天", "日")), start=int(first), end=int(last or first))
            if "优先连堂" in chosen:
                fields["prefer_pair"] = True
            if "并打开日程" in chosen:
                fields["open_schedule"] = True
        return app.activity_preview(fields)
    clocks = re.fullmatch(r"确认组队作息\s+(我的课表|预设|\{.*\})", text, re.S)
    if clocks:
        value = clocks[1]
        fields = {"slot": context.get("activity")}
        if value.startswith("{"):
            fields["clocks"] = _object(value)
        else:
            fields["choice"] = "personal" if value == "我的课表" else "preset"
        return app.activity_clocks(fields)
    if text in {"制定小组日程", "从空档制定日程"}:
        slot_data = app._get_draft(context.get("activity"), "activity_slot")
        return app.planning.run({"operation": "start", "group_token": slot_data["group_token"],
                                 "day": slot_data["day"], "first": slot_data["start"], "last": slot_data["end"]})
    add = re.fullmatch(r"(?:确认添加活动|确认留出时间)(?:\s+(.*))?", text)
    if add:
        remaining = add[1] or ""
        export_ics = bool(re.search(r"(?:并|同时)导出(?:日历|ICS)$", remaining, re.I))
        remaining = re.sub(r"(?:并|同时)导出(?:日历|ICS)$", "", remaining, flags=re.I).strip()
        title, _, room = re.split(r"\s*(地点|教室)[:\uff1a]\s*", remaining, maxsplit=1) if re.search(r"(?:地点|教室)[:\uff1a]", remaining) else (remaining, "", "")
        fields = {"slot": context.get("activity"), "room": room.strip(), "export_ics": export_ics}
        if title.strip():
            fields["title"] = title.strip()
        return app.activity(fields)

    bg_preview = re.fullmatch(r"预览\s*(电脑|手机)壁纸背景\s*(?:[:\uff1a]\s*)?(.+)", text)
    if bg_preview:
        background = normalize(bg_preview[2])
        fmt = "phone" if bg_preview[1] == "手机" else "desktop"
        value = app.wallpaper_background_preview({"background": background, "format": fmt})
        return {"type": "background_preview", **value, "message": f"{bg_preview[1]}背景预览: {BACKGROUNDS[background]}"}
    if "壁纸" in text and (text.startswith("导出") or re.search(r"背景[:\uff1a]|附件(?:作为|作|做)壁纸背景", text)):
        fields = {**payload, "formats": payload.get("formats", formats_for(text))}
        week = re.search(_WEEK, text)
        if week:
            fields["wallpaper_week"] = _number(week[1])
        if re.search(r"附件(?:作为|作|做)壁纸背景", text):
            fields["wallpaper_attachment"] = True
        else:
            background = re.search(r"背景[:\uff1a]\s*([^\s,\uff0c;]+)", text)
            if background:
                fields["wallpaper"] = {"background": normalize(background[1])}
        return app.run("prepare", fields)
    return None
