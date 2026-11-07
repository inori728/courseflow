"""Select exact occurrences, preview each move, then save after confirmation."""
from __future__ import annotations

import copy
import json
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from .. import service
from ..model import DAYS
from ..notice import NoticeIntent
from .dialogs import ACCENT, Button, OptionMenu, INK, MUTED, Modal, label


class NoticeDialog(Modal):
    def __init__(self, master, use_ai=True):
        super().__init__(master, "通知调课" if use_ai else "手动调课 / 停课", 1030, 820)
        self.snapshot = copy.deepcopy(self.app.tt)
        self.signature = service.timetable_signature(self.snapshot)
        self.preview = None
        self.preview_form = None
        self.candidates = []
        self.candidate_widgets = {}
        self.use_ai = use_ai
        label(self, "读懂通知, 选对课次, 更新当前课表" if use_ai else "选择课次并填写调整内容", 23).pack(anchor="w", padx=24, pady=(20, 5))
        label(self, "同名课程有多次安排时请勾选; 每次课都可以单独填写目标周, 星期和节次.", 12, MUTED).pack(anchor="w", padx=24, pady=(0, 10))
        body = ctk.CTkScrollableFrame(self, fg_color="white", corner_radius=14)
        body.pack(fill="both", expand=True, padx=24)
        if use_ai:
            self.text = ctk.CTkTextbox(body, height=90, font=("Microsoft YaHei UI", 13), border_width=1, border_color="#dbe3f0")
            self.text.pack(fill="x", padx=14, pady=(14, 6))
            self.text.insert("1.0", "")
            self.parse_button = Button(body, text="解析通知", height=33, fg_color=ACCENT, command=self.parse)
            self.parse_button.pack(anchor="e", padx=14, pady=(0, 10))
        self.fields = {}
        source = ctk.CTkFrame(body, fg_color="#f3f6fc")
        source.pack(fill="x", padx=14, pady=8)
        source.grid_columnconfigure(0, weight=2)
        source.grid_columnconfigure((1, 2, 3), weight=1)
        self._field(source, "course_name", "课程名称", 0, 0, sorted(set(c.name for c in self.snapshot.courses)), combo=True)
        self._field(source, "source_week", "原周次", 0, 1)
        self._field(source, "source_day", "原星期(可不限)", 0, 2, ["不限"] + DAYS)
        self._field(source, "source_periods", "原节次(可留空)", 0, 3)
        target = ctk.CTkFrame(body, fg_color="#f3f6fc")
        target.pack(fill="x", padx=14, pady=8)
        for column in range(4):
            target.grid_columnconfigure(column, weight=1)
        self._field(target, "action", "调整类型", 0, 0, ["调课", "停课", "换教室"])
        self._field(target, "target_week", "目标周次", 0, 1)
        self._field(target, "target_day", "目标星期", 0, 2, ["待补充"] + DAYS)
        self._field(target, "target_periods", "目标节次(如5-6)", 0, 3)
        self._field(target, "target_time", "开始钟点(如14:00)", 2, 0)
        self._field(target, "target_end_time", "结束钟点(可留空)", 2, 1)
        self._field(target, "room", "新地点(留空为不变)", 2, 2)
        self.keep_duration = tk.BooleanVar(value=True)
        self.keep_day = tk.BooleanVar(value=False)
        options = ctk.CTkFrame(body, fg_color="transparent")
        options.pack(fill="x", padx=17, pady=8)
        ctk.CTkCheckBox(options, text="时长不变", variable=self.keep_duration, command=self.invalidate).pack(side="left", padx=(0, 20))
        ctk.CTkCheckBox(options, text="星期不变", variable=self.keep_day, command=self.invalidate).pack(side="left")
        Button(options, text="查找 / 刷新候选", width=150, fg_color=ACCENT, command=self.find).pack(side="right")
        self.candidate_area = ctk.CTkFrame(body, fg_color="transparent", height=1)
        self.candidate_area.pack(fill="x", padx=14, pady=5)
        self.result_box = ctk.CTkTextbox(body, height=125, fg_color="#f3f6fc", font=("Microsoft YaHei UI", 12))
        self.result_box.pack(fill="x", padx=14, pady=12)
        self.show_result("先解析通知或填写原课程信息, 再查找需要调整的课次.")
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=16)
        Button(footer, text="取消", width=90, fg_color="#dfe5f0", text_color=INK, command=self.close).pack(side="left")
        self.apply_button = Button(footer, text="确认修改当前课表", width=180, fg_color=ACCENT, state="disabled", command=self.apply)
        self.apply_button.pack(side="right", padx=(10, 0))
        Button(footer, text="预览修改与冲突", width=160, fg_color="#e4eaf9", text_color=ACCENT, command=self.make_preview).pack(side="right")
        try:
            week = service.current_week(self.snapshot)
        except ValueError:
            week = 1
        self.put("source_week", str(max(1, min(week, self.snapshot.weeks_total))))

    def _field(self, parent, key, title, row, column, values=None, combo=False):
        label(parent, title, 11, MUTED).grid(row=row, column=column, padx=10, pady=(9, 3), sticky="w")
        if values is None:
            widget = ctk.CTkEntry(parent, height=33)
            widget.bind("<KeyRelease>", lambda event: self.invalidate())
        elif combo:
            widget = ctk.CTkComboBox(parent, values=values, height=33, command=lambda value: self.invalidate())
            widget.bind("<KeyRelease>", lambda event: self.invalidate())
        else:
            widget = OptionMenu(parent, values=values, height=33, fg_color="#e4eaf9", text_color=INK, command=lambda value: self.invalidate())
        widget.grid(row=row + 1, column=column, padx=10, pady=(0, 10), sticky="ew")
        self.fields[key] = widget

    def put(self, key, value):
        widget = self.fields[key]
        if isinstance(widget, ctk.CTkEntry):
            widget.delete(0, "end")
            widget.insert(0, value or "")
        else:
            widget.set(value or "")

    def show_result(self, text):
        self.result_box.configure(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", text)
        self.result_box.configure(state="disabled")

    def invalidate(self):
        self.preview = None
        if hasattr(self, "apply_button"):
            self.apply_button.configure(state="disabled")

    def intent(self):
        values = {key: widget.get().strip() for key, widget in self.fields.items()}
        values["action"] = {"调课": "move", "停课": "cancel", "换教室": "room"}[values["action"]]
        values["source_day"] = None if values["source_day"] in {"", "不限"} else values["source_day"]
        values["target_day"] = None if values["target_day"] in {"", "待补充"} else values["target_day"]
        values["room"] = values["room"] or None
        values["keep_duration"], values["keep_day"] = self.keep_duration.get(), self.keep_day.get()
        return NoticeIntent.from_payload(values, self.snapshot.weeks_total)

    def parse(self):
        text = self.text.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showinfo("请先输入通知", "请输入或粘贴调课通知.", parent=self)
            return
        self.invalidate()
        self.parse_button.configure(state="disabled")
        started = self.app.run_task(lambda: service.interpret_notification(self.snapshot, text), self.parsed,
                                    "正在理解通知, 不会直接修改课表...", self.failed)
        if not started:
            self.parse_button.configure(state="normal")

    def failed(self, exc):
        if self.winfo_exists():
            self.parse_button.configure(state="normal")
            self.show_result(str(exc))

    def parsed(self, intent):
        if not self.winfo_exists():
            return
        self.parse_button.configure(state="normal")
        if service.timetable_signature(self.app.tt) != self.signature:
            self.show_result("当前课表已变化, 请关闭窗口后重新解析.")
            return
        self.put("course_name", intent.course_name)
        self.put("source_week", str(intent.source_week or ""))
        self.put("source_day", DAYS[intent.source_day] if intent.source_day is not None else "不限")
        self.put("source_periods", intent.source_periods)
        self.put("action", {"move": "调课", "cancel": "停课", "room": "换教室"}[intent.action])
        self.put("target_week", str(intent.target_week or ""))
        self.put("target_day", DAYS[intent.target_day] if intent.target_day is not None else "待补充")
        for key in ("target_periods", "target_time", "target_end_time", "room"):
            self.put(key, getattr(intent, key))
        self.keep_duration.set(intent.keep_duration)
        self.keep_day.set(intent.keep_day)
        self.find()
        if intent.notes:
            self.show_result("AI 提示:\n" + "\n".join(intent.notes) + "\n请核对字段, 选择具体课次后预览.")

    def find(self):
        try:
            intent = self.intent()
            self.candidates = service.notice_candidates(self.snapshot, intent)
            for child in self.candidate_area.winfo_children():
                child.destroy()
            self.candidate_widgets = {}
            header = ctk.CTkFrame(self.candidate_area, fg_color="transparent")
            header.pack(fill="x", pady=(8, 6))
            label(header, f"找到 {len(self.candidates)} 次课, 请选择需要调整的课次", 13).pack(side="left")
            Button(header, text="全选", width=65, fg_color="#e4eaf9", text_color=ACCENT, command=lambda: self.select_all(True)).pack(side="right", padx=4)
            Button(header, text="清空", width=65, fg_color="#e4eaf9", text_color=ACCENT, command=lambda: self.select_all(False)).pack(side="right", padx=4)
            for candidate in self.candidates:
                row = ctk.CTkFrame(self.candidate_area, fg_color="#f3f6fc")
                row.pack(fill="x", pady=4)
                row.grid_columnconfigure(0, weight=1)
                variable = tk.BooleanVar(value=len(self.candidates) == 1)
                ctk.CTkCheckBox(row, text=candidate.describe(), variable=variable, command=self.invalidate,
                               font=("Microsoft YaHei UI", 13)).grid(row=0, column=0, sticky="w", padx=8, pady=10)
                week = ctk.CTkEntry(row, width=58, placeholder_text="周次")
                week.insert(0, str(intent.target_week or candidate.occurrence.week))
                week.grid(row=0, column=1, padx=4)
                day = OptionMenu(row, width=98, values=["待补充"] + DAYS, fg_color="#e4eaf9", text_color=INK, command=lambda value: self.invalidate())
                day.set(DAYS[candidate.occurrence.day] if intent.keep_day or intent.action == "room" else (DAYS[intent.target_day] if intent.target_day is not None else "待补充"))
                day.grid(row=0, column=2, padx=4)
                periods = ctk.CTkEntry(row, width=80, placeholder_text="目标节次")
                periods.insert(0, intent.target_periods)
                periods.grid(row=0, column=3, padx=(4, 8))
                week.bind("<KeyRelease>", lambda event: self.invalidate())
                periods.bind("<KeyRelease>", lambda event: self.invalidate())
                self.candidate_widgets[candidate.token] = (variable, week, day, periods)
            self.invalidate()
            self.show_result("未找到匹配课次, 请核对课程名称, 原周次及筛选条件." if not self.candidates else
                             "每一行右侧依次为目标周, 星期和节次. 目标节次留空时使用上方钟点或沿用原节次.\n修改上方默认目标后请刷新候选, 最终以下方每行的目标为准.\n全选会分别调整每次课. 确认应用会保存当前课表及本次调整.")
        except ValueError as exc:
            self.show_result(str(exc))

    def select_all(self, checked):
        for variable, week, day, periods in self.candidate_widgets.values():
            variable.set(checked)
        self.invalidate()

    def form_snapshot(self):
        return json.dumps({
            "fields": {key: widget.get() for key, widget in self.fields.items()},
            "keep": [self.keep_day.get(), self.keep_duration.get()],
            "candidates": {key: [variable.get(), week.get(), day.get(), periods.get()]
                           for key, (variable, week, day, periods) in self.candidate_widgets.items()},
        }, ensure_ascii=False, sort_keys=True)

    def make_preview(self):
        try:
            if service.timetable_signature(self.app.tt) != self.signature:
                raise ValueError("课表已变化, 请关闭窗口后重新选择.")
            intent = self.intent()
            selected, overrides = [], {}
            for candidate in self.candidates:
                variable, week, day, periods = self.candidate_widgets[candidate.token]
                if not variable.get():
                    continue
                selected.append(candidate)
                overrides[candidate.token] = {
                    "target_week": int(week.get()),
                    "target_day": DAYS.index(day.get()) if day.get() in DAYS else None,
                    "target_periods": periods.get().strip(),
                }
            self.preview = service.notice_preview(self.snapshot, intent, selected, overrides)
            self.preview_form = self.form_snapshot()
            lines = []
            for original, target in self.preview.rows:
                lines.extend(["原: " + original, "新: " + target, ""])
            if self.preview.new_conflicts:
                lines.append("存在新的时间冲突, 请修改目标时间后重新预览:")
                lines.extend(self.preview.new_conflicts)
            else:
                lines.append("未发现新增时间冲突. 确认后会修改当前课表并保存, 随即在应用内显示调整后的周课表.")
            self.show_result("\n".join(lines))
            self.apply_button.configure(state="disabled" if self.preview.new_conflicts else "normal")
        except ValueError as exc:
            self.invalidate()
            self.show_result(str(exc))

    def apply(self):
        try:
            if self.preview is None or self.form_snapshot() != self.preview_form:
                raise ValueError("内容已经变化, 请先重新预览.")
            if self.app.persist_adjustment(self.preview):
                self.close()
                self.app.go("review")
        except (ValueError, OSError) as exc:
            self.show_result(str(exc))
            self.apply_button.configure(state="disabled")
