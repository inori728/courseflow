"""Desktop group schedule editing, comparison, and card preview."""
from __future__ import annotations

from datetime import date, datetime
import re
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from .. import service
from ..planning import clock_windows, member_labels, require_free, schedule_draft, selected_slot, slot_fields, suggest_agenda
from ..schedule_card import CARD_STYLES, render_schedule_card, write_schedule_card
from ..semester import _tzinfo
from ..settings import AI_REQUIRED
from .ai_dialog import AISettingsDialog
from .dialogs import ACCENT, Button, INK, MUTED, Modal, OptionMenu, label
from .styles import LIGHT


class ScheduleFields(ctk.CTkFrame):
    def __init__(self, master, draft):
        super().__init__(master, fg_color="transparent")
        self.fields = {}
        times = ctk.CTkFrame(self, fg_color="transparent")
        times.pack(fill="x")
        for index, (key, title) in enumerate((("date", "日期"), ("start", "开始"), ("end", "结束"))):
            times.grid_columnconfigure(index, weight=1)
            column = ctk.CTkFrame(times, fg_color="transparent")
            column.grid(row=0, column=index, padx=(0, 7), sticky="ew")
            self.add_field(column, key, title)
        self.add_field(self, "title", "事项")
        self.add_field(self, "room", "集合地点")
        self.add_field(self, "notes", "说明")
        self.add_field(self, "members", "成员或代号 (每人一行, 保持顺序)", lines=55)
        self.add_field(self, "agenda", "现场议程 (每行写 分钟 | 内容)", lines=85)
        self.add_field(self, "prep", "会前分工 (每行写 负责人 / 负责人 | 事项)", lines=85)
        self.fill(draft)

    def add_field(self, parent, key, title, lines=0):
        label(parent, title, 13, MUTED).pack(anchor="w", pady=(7, 3))
        widget = ctk.CTkTextbox(parent, height=lines, border_width=1, border_color="#cbd5e3") if lines else ctk.CTkEntry(parent)
        widget.pack(fill="x")
        self.fields[key] = widget

    def fill(self, draft):
        values = dict(draft)
        values["members"] = "\n".join(draft["members"])
        values["agenda"] = "\n".join(f"{item['minutes']} | {item['title']}" for item in draft["agenda"])
        values["prep"] = "\n".join(f"{' / '.join(item['owners'])} | {item['title']}" for item in draft["prep"])
        for key, widget in self.fields.items():
            start = "1.0" if key in {"agenda", "prep", "members"} else 0
            widget.delete(start, "end")
            widget.insert(start, values[key])

    def values(self):
        fields = {key: self.fields[key].get() for key in ("date", "start", "end", "title", "room", "notes")}
        fields["members"] = self.fields["members"].get("1.0", "end-1c").splitlines()
        fields["agenda"], fields["prep"] = [], []
        for key in ("agenda", "prep"):
            lines = self.fields[key].get("1.0", "end-1c")
            for line in filter(str.strip, lines.splitlines()):
                left, separator, title = line.partition("|")
                if not separator:
                    raise ValueError("议程和分工请用 | 分隔钟点或负责人与内容.")
                if key == "agenda":
                    try:
                        minutes = int(left)
                    except ValueError as exc:
                        raise ValueError("每段现场议程请填写整数分钟数.") from exc
                    fields[key].append({"minutes": minutes, "title": title})
                else:
                    owners = [name.strip() for name in re.split(r"[/,\uff0c\u3001]", left) if name.strip()]
                    fields[key].append({"owners": owners, "title": title})
        return fields


def _summary(draft):
    rows = [draft["title"], f"{draft['date']}  {draft['start']}-{draft['end']}",
            f"集合地点: {draft['room'] or '待定'}", draft["notes"], "现场议程"]
    rows += [f"{item['minutes']} 分钟 | {item['title']}" for item in draft["agenda"]]
    rows.append("会前分工")
    rows += [f"{' / '.join(item['owners'])} | {item['title']}" for item in draft["prep"]]
    return "\n".join(rows)


class ScheduleComparison(Modal):
    def __init__(self, master, original, review):
        super().__init__(master, "核对日程修改", 1000, 730)
        self.schedule = master
        self.original = original
        label(self, "核对日程修改", 22).pack(anchor="w", padx=20, pady=(14, 2))
        label(self, f"你的要求: {review['request']}", 13, MUTED, wraplength=690, justify="left").pack(anchor="w", padx=20)
        if review["summary"]:
            label(self, review["summary"], 13, INK, wraplength=690, justify="left").pack(anchor="w", padx=20, pady=6)
        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=9)
        columns.grid_rowconfigure(1, weight=1)
        for index, title in enumerate(("修改前", "修改后 (可编辑)")):
            columns.grid_columnconfigure(index, weight=1, uniform="comparison")
            label(columns, title, 15).grid(row=0, column=index, sticky="w", padx=8)
        before = ctk.CTkTextbox(columns, wrap="word")
        before.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=6)
        before.insert("1.0", _summary(original))
        before.configure(state="disabled")
        after = ctk.CTkScrollableFrame(columns, fg_color="white")
        after.grid(row=1, column=1, sticky="nsew", pady=6)
        self.fields = ScheduleFields(after, review["draft"])
        self.fields.pack(fill="x", padx=8, pady=(0, 8))
        Button(self, text="应用修改", fg_color=ACCENT, command=self.apply).pack(anchor="e", padx=20, pady=(2, 12))

    def apply(self):
        try:
            self.schedule.apply_review(self.fields.values(), self.original)
        except (ValueError, OSError) as exc:
            messagebox.showerror("修改未应用", str(exc), parent=self)
            return
        self.close()


class ScheduleCardPreview(Modal):
    def __init__(self, master, draft):
        super().__init__(master, "日程卡预览", 620, 730)
        self.schedule = master
        self.draft = draft
        self.style = "green"
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=12)
        OptionMenu(header, values=list(CARD_STYLES.values()), command=self.show).pack(side="left")
        Button(header, text="导出 PNG", fg_color=ACCENT, command=self.export).pack(side="right")
        board = ctk.CTkScrollableFrame(self, fg_color="white")
        board.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self.preview = label(board, "")
        self.preview.pack(pady=12)
        self.show(CARD_STYLES[self.style])

    def show(self, name):
        self.style = next(key for key, value in CARD_STYLES.items() if value == name)
        image = render_schedule_card(self.draft, self.style)
        image.thumbnail((480, 1600), Image.Resampling.LANCZOS)
        self.preview.configure(image=ctk.CTkImage(image, size=image.size))

    def export(self):
        try:
            draft = self.schedule.checked(self.draft, required=True)
            target = filedialog.asksaveasfilename(parent=self, title="导出日程卡", initialfile="小组日程安排.png",
                                                  defaultextension=".png", filetypes=[("PNG 图片", "*.png")])
            if target:
                write_schedule_card(draft, self.style, target)
                messagebox.showinfo("已导出日程卡", target, parent=self)
        except (ValueError, OSError) as exc:
            messagebox.showerror("日程卡未导出", str(exc), parent=self)


class GroupScheduleDialog(Modal):
    def __init__(self, view, result, day, first, last):
        draft = schedule_draft(selected_slot(result, day, first, last), result.names)
        super().__init__(view.app, "制定小组日程", 1030, 760)
        self.view = view
        self.previous = None
        label(self, "制定小组日程", 24).pack(anchor="w", padx=20, pady=(15, 3))
        self.status = label(self, "可从左侧选空档, 也可在共同空闲范围内填写具体钟点.", 13, MUTED)
        self.status.pack(anchor="w", padx=20)
        columns = ctk.CTkFrame(self, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=20, pady=10)
        columns.grid_columnconfigure(1, weight=1)
        columns.grid_rowconfigure(0, weight=1)
        matches = ctk.CTkScrollableFrame(columns, width=215, fg_color="white", label_text="本周共同空档")
        matches.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.slot_buttons = {}
        for index in range(7):
            for start, end in clock_windows(result, index):
                fields = slot_fields(start, end)
                item = (fields["date"], fields["start"], fields["end"])
                button = Button(matches, text=f"{item[0]}  {item[1]}-{item[2]}", fg_color="#e3f4ec", text_color=INK,
                                command=lambda slot=fields: self.select(slot))
                button.pack(fill="x", padx=3, pady=3)
                self.slot_buttons[item] = button
        form = ctk.CTkScrollableFrame(columns, fg_color="white")
        form.grid(row=0, column=1, sticky="nsew")
        self.fields = ScheduleFields(form, draft)
        self.fields.pack(fill="x", padx=10, pady=(0, 8))
        label(form, "AI 目标或改动要求", 13, MUTED).pack(anchor="w", padx=10)
        label(form, "可直接描述想做什么. AI 会补齐空白的事项, 生成议程和分工.",
              12, MUTED, wraplength=460, justify="left").pack(anchor="w", padx=10, pady=(2, 0))
        self.prompt = ctk.CTkTextbox(form, height=56, border_width=1, border_color="#cbd5e3")
        self.prompt.pack(fill="x", padx=10, pady=(4, 8))
        bot = ctk.CTkFrame(form, fg_color="transparent")
        bot.pack(fill="x", padx=10, pady=(0, 12))
        Button(bot, text="AI 拟议程", fg_color=LIGHT, text_color=INK, command=lambda: self.ask_ai(False)).pack(side="left", padx=(0, 6))
        Button(bot, text="AI 改日程", fg_color=LIGHT, text_color=INK, command=lambda: self.ask_ai(True)).pack(side="left")
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=(0, 14))
        self.undo_button = Button(actions, text="撤销更改", fg_color=LIGHT, text_color=INK, state="disabled", command=self.undo)
        self.undo_button.pack(side="left")
        Button(actions, text="核对空档", fg_color=LIGHT, text_color=INK, command=self.check).pack(side="left", padx=8)
        Button(actions, text="预览日程卡", fg_color=ACCENT, command=self.preview).pack(side="right")
        label(actions, "日程卡用于分享. 要把时间留在个人课表, 请在组队页添加活动.",
              12, MUTED, wraplength=340, justify="left").pack(side="right", padx=10)
        self.highlight(draft)

    def highlight(self, fields):
        selection = (fields["date"], fields["start"], fields["end"])
        for key, button in self.slot_buttons.items():
            button.configure(border_width=2 if key == selection else 0, border_color=ACCENT)

    def select(self, fields):
        for key, value in fields.items():
            widget = self.fields.fields[key]
            widget.delete(0, "end")
            widget.insert(0, value)
        self.highlight(fields)
        self.status.configure(text="已带入所选时段. 修改后可重新核对空档.")

    def checked(self, fields, required=False):
        cards = self.view.current_cards()
        if not cards:
            raise ValueError("请先添加成员课表或忙闲卡.")
        when = date.fromisoformat(fields["date"])
        week = (when - cards[0].semester_start).days // 7 + 1
        result = service.group_free(cards, week, 1)
        require_free(result, fields)
        return schedule_draft(fields, member_labels(fields["members"], result.names), require_title=required)

    def check(self):
        try:
            fields = self.checked(self.fields.values())
            self.highlight(fields)
            self.status.configure(text=f"已核对全员空闲: {fields['date']}  {fields['start']}-{fields['end']}")
        except (ValueError, OSError) as exc:
            self.failed(exc)

    def ask_ai(self, revise):
        try:
            draft = self.checked(self.fields.values())
            text = self.prompt.get("1.0", "end-1c").strip()
            if not 1 <= len(text) <= 2000:
                raise ValueError("请填写日程目标或修改要求, 最多 2000 字.")
            try:
                config = service.ai_settings()
                config.validate()
            except (ValueError, OSError):
                config = None
            if not config or not config.vision_verified:
                self.status.configure(text=AI_REQUIRED)
                AISettingsDialog(self, on_verified=lambda: self.ask_ai(revise))
                return
            today = datetime.now(_tzinfo(self.view.current_cards()[0].timezone)[0]).date()
            self.app.run_task(lambda: suggest_agenda(config, draft, text, revise=revise, today=today,
                                                     check_slot=self.checked),
                              lambda review: self.show_review(draft, review), "正在生成日程草稿...", self.failed)
        except (ValueError, OSError) as exc:
            self.failed(exc)

    def show_review(self, original, review):
        if self.winfo_exists():
            try:
                self.checked(review["draft"], required=True)
                ScheduleComparison(self, original, review)
            except (ValueError, OSError) as exc:
                self.failed(exc)

    def apply_review(self, fields, original):
        current = self.checked(self.fields.values())
        if current != original:
            raise ValueError("当前草稿在生成对照时已有改动. 请重新生成修改.")
        draft = self.checked(fields, required=True)
        self.previous = current
        self.fields.fill(draft)
        self.highlight(draft)
        self.undo_button.configure(state="normal")
        self.status.configure(text="已应用日程修改.")

    def undo(self):
        if self.previous is not None:
            self.fields.fill(self.previous)
            self.highlight(self.previous)
            self.previous = None
            self.undo_button.configure(state="disabled")
            self.status.configure(text="已恢复上一次修改前的日程草稿.")

    def preview(self):
        try:
            ScheduleCardPreview(self, self.checked(self.fields.values(), required=True))
        except (ValueError, OSError) as exc:
            self.failed(exc)

    def failed(self, error):
        if self.winfo_exists():
            messagebox.showerror("请核对小组日程", str(error), parent=self)
