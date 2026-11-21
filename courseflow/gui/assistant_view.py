"""Scrollable desktop dialogue with a persistent composer and local help."""
from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from ..guide import usage_guide
from ..harness import Harness, SettingsRequired
from .ai_dialog import AISettingsDialog
from .dialogs import BG, INK, LIGHT, MUTED, Button, label
from .styles import LIGHT_ACTIVE, LIGHT_HOVER


RESULT_LABELS = {"prepare": "核对导入", "preview": "查看预览", "group_prepare": "核对成员资料",
                 "group_result": "查看忙闲图", "schedule": "核对并预览日程卡", "activity": "核对选定时段",
                 "todos": "打开待办", "todo_reserve": "选空档", "agenda": "查看课表",
                 "saved": "查看导出结果"}


class AssistantView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=BG)
        self.app = app
        self.backend = Harness(app.source)
        self.context, self.messages, self.files = {}, [], []
        self.guide = usage_guide(commands=False)
        self.mode = "chat"
        self.guide_open = False
        self.working = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=28, pady=(16, 9))
        label(head, "课表助手", 23).pack(side="left")
        self.guide_button = Button(head, text="使用指引", fg_color=LIGHT, command=self.toggle_guide)
        self.guide_button.pack(side="right")
        self.dialogue = ctk.CTkScrollableFrame(self, fg_color="white", corner_radius=12)
        self.dialogue.grid(row=1, column=0, sticky="nsew", padx=28, pady=(0, 8))

        compose = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color="#dbe3ed")
        compose.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 10))
        self.feedback = ctk.CTkFrame(compose, fg_color=LIGHT)
        self.feedback_text = label(self.feedback, "", 13, INK, wraplength=835, justify="left")
        self.feedback_text.pack(side="left", padx=10, pady=4)
        self.setup = Button(self.feedback, text="设置 AI 接口", width=100, command=self.open_settings)
        self.attachments = ctk.CTkFrame(compose, fg_color="transparent")
        self.attachments.pack(fill="x", padx=8)
        self.input = ctk.CTkTextbox(compose, height=82, wrap="word", fg_color="white", text_color=INK)
        self.input.pack(fill="x", padx=10, pady=(7, 1))
        self.input.bind("<Control-Return>", lambda event: self.send() or "break")
        controls = ctk.CTkFrame(compose, fg_color="transparent")
        controls.pack(fill="x", padx=10, pady=(0, 8))
        self.attach_button = Button(controls, text="附件", width=60, fg_color=LIGHT, command=self.add_files)
        self.attach_button.pack(side="left")
        self.switch = ctk.CTkSegmentedButton(
            controls, values=["聊天", "课表操作"], command=self.set_mode, text_color=INK,
            fg_color=LIGHT, selected_color=LIGHT_ACTIVE, selected_hover_color=LIGHT_ACTIVE,
            unselected_color=LIGHT, unselected_hover_color=LIGHT_HOVER,
        )
        self.switch.set("聊天")
        self.switch.pack(side="left", padx=8)
        self.send_button = Button(controls, text="发送", width=74, command=self.send)
        self.send_button.pack(side="right")

    def activate(self):
        if self.backend.source_path() != self.app.source.resolve():
            self.backend = Harness(self.app.source)
            self.context.clear()
            self.messages.clear()
        self.render()
        self.input.focus_set()

    def fill_example(self):
        self.input.delete("1.0", "end")
        self.input.insert("1.0", self.guide["sample"])
        self.input.focus_set()

    def toggle_guide(self):
        self.guide_open = not self.guide_open
        self.guide_button.configure(text="收起指引" if self.guide_open else "使用指引")
        self.render()

    def render_guide(self):
        guide = ctk.CTkFrame(self.dialogue, fg_color="transparent")
        guide.pack(fill="x", padx=16, pady=12)
        for section in self.guide["sections"]:
            label(guide, section["title"], 18).pack(anchor="w", pady=(0, 8))
            if section.get("layout"):
                self.render_assistant_help(guide, section["layout"])
            else:
                text = section["body"].replace("**", "").replace(chr(96), "")
                label(guide, text, 14, INK, justify="left", wraplength=850).pack(anchor="w")
        self.after_idle(lambda: self.dialogue._parent_canvas.yview_moveto(0))

    def render_assistant_help(self, master, layout):
        notes = ctk.CTkFrame(master, fg_color="transparent")
        notes.pack(fill="x", pady=(0, 16))
        notes.grid_columnconfigure((0, 1), weight=1, uniform="guide")
        for index, item in enumerate(layout["notes"]):
            setup = index > 1
            card = ctk.CTkFrame(notes, fg_color=LIGHT, corner_radius=9)
            card.grid(row=1 if setup else 0, column=0 if setup else index, columnspan=2 if setup else 1,
                      sticky="nsew", padx=4, pady=3)
            label(card, item["title"], 15).pack(anchor="w", padx=10, pady=(7, 2))
            label(card, item["text"], 13, INK, wraplength=850 if setup else 382, justify="left").pack(
                anchor="w", padx=10, pady=(0, 8))

        label(master, "参考例句", 16).pack(anchor="w", pady=(0, 2))
        label(master, layout["hint"], 13, MUTED, wraplength=850, justify="left").pack(anchor="w", pady=(0, 8))
        examples = ctk.CTkFrame(master, fg_color="white", border_width=1, border_color=LIGHT)
        examples.pack(fill="x", pady=(0, 16))
        rows = []
        opened = None

        def toggle(index):
            nonlocal opened
            previous = opened
            if previous is not None:
                title, button, body = rows[previous]
                body.pack_forget()
                button.configure(text=f"\u25b8  {title}", fg_color="transparent")
            opened = None if previous == index else index
            if opened is not None:
                title, button, body = rows[opened]
                button.configure(text=f"\u25be  {title}", fg_color=LIGHT)
                body.pack(fill="x", padx=12, pady=(1, 9))

        for index, item in enumerate(layout["examples"]):
            row = ctk.CTkFrame(examples, fg_color="transparent")
            row.pack(fill="x", padx=3, pady=1)
            button = Button(row, text=f"\u25b8  {item['title']}", fg_color="transparent", text_color=INK,
                            anchor="w", height=34, command=lambda choice=index: toggle(choice))
            button.pack(fill="x")
            body = ctk.CTkFrame(row, fg_color="transparent")
            if item["hint"]:
                label(body, item["hint"], 13, MUTED, justify="left", wraplength=825).pack(anchor="w", pady=(0, 2))
            label(body, item["text"], 14, INK, justify="left", wraplength=825).pack(anchor="w")
            rows.append((item["title"], button, body))

    def render(self):
        for child in self.dialogue.winfo_children():
            child.destroy()
        if self.guide_open:
            self.render_guide()
            return
        if not self.messages:
            if not self.backend.settings({})["verified"]:
                row = ctk.CTkFrame(self.dialogue, fg_color="transparent")
                row.pack(anchor="w", padx=12, pady=(10, 4))
                label(row, "AI 待配置", 13, MUTED).pack(side="left", padx=(0, 9))
                Button(row, text="设置 AI 接口", width=101, fg_color=LIGHT,
                       command=self.open_settings).pack(side="left")
            label(self.dialogue, "查课\u3001导入截图\u3001调课或安排小组日程.", 16).pack(anchor="w", padx=12, pady=(12, 4))
            label(self.dialogue, "要查课或改课表, 先切到课表操作.", 13, MUTED).pack(anchor="w", padx=12, pady=3)
            Button(self.dialogue, text=f"填入示例 \u203a {self.guide['sample']}", fg_color=LIGHT,
                   command=self.fill_example).pack(anchor="w", padx=12, pady=10)
            return
        for item in self.messages:
            own = item["role"] == "user"
            frame = ctk.CTkFrame(self.dialogue, fg_color=LIGHT if own else "transparent", corner_radius=10)
            frame.pack(anchor="e" if own else "w", padx=9, pady=6)
            if item.get("attachments"):
                label(frame, " / ".join(item["attachments"]), 13, MUTED, wraplength=750).pack(anchor="w", padx=10, pady=(6, 0))
            label(frame, item["message"], 15, INK, justify="left", wraplength=870).pack(anchor="w", padx=10, pady=6)
            state = "normal" if not self.working and self.mode == "operate" else "disabled"
            for slot in item.get("slots", []):
                Button(frame, text=f"候选 {slot['number']} · {slot['label']} / 选这段", state=state, fg_color=LIGHT,
                       command=lambda choice=slot, reply=item: self.choose(
                           {"group_token": reply["result"]["token"], "number": choice["number"], "goal": reply.get("goal")})).pack(
                               anchor="w", padx=10, pady=3)
            for choice in item.get("choices", []):
                Button(frame, text=choice["label"], state=state, fg_color=LIGHT,
                       command=lambda option=choice: self.choose(option)).pack(anchor="w", padx=10, pady=3)
            value = item.get("result")
            if value:
                title = RESULT_LABELS.get(value["type"], "查看结果")
                if value["type"] == "saved" and value.get("updated"):
                    title = "查看保存记录"
                Button(frame, text=title, state=state, fg_color=LIGHT,
                       command=lambda reply=item: self.open_result(reply)).pack(anchor="w", padx=10, pady=(3, 7))
        self.after_idle(lambda: self.dialogue._parent_canvas.yview_moveto(1))

    def set_mode(self, value):
        self.mode = "operate" if value == "课表操作" else "chat"
        self.show_feedback("")
        self.render()

    def show_feedback(self, message, setup=False):
        self.feedback.pack_forget()
        self.setup.pack_forget()
        if message:
            explanation = message + (" 已保留当前输入和附件." if setup else "")
            self.feedback_text.configure(text=explanation)
            if setup:
                self.setup.pack(side="right", padx=7, pady=5)
            self.feedback.pack(fill="x", padx=8, pady=(8, 0), before=self.attachments)

    def open_settings(self):
        AISettingsDialog(self.app, on_verified=lambda: (self.show_feedback("AI 已就绪, 可以接着发送."), self.render()))

    def add_files(self):
        selected = filedialog.askopenfilenames(parent=self.app, title="添加课表附件",
            filetypes=[("课表 / 截图 / 忙闲卡", "*.png *.jpg *.jpeg *.gif *.webp *.yaml *.yml *.xlsx *.csv *.docx *.pdf *.busycard *.txt")])
        if not selected:
            return
        paths = list(dict.fromkeys(self.files + [Path(path) for path in selected]))
        try:
            if len(paths) > 20 or sum(path.stat().st_size for path in paths) > 12 * 1024 * 1024:
                raise ValueError("每次最多添加 20 份附件, 总计不超过 12 MB.")
        except (ValueError, OSError) as exc:
            self.show_feedback(str(exc))
            return
        self.files = paths
        self.update_files()

    def update_files(self):
        for child in self.attachments.winfo_children():
            child.destroy()
        for path in self.files:
            Button(self.attachments, text=path.name + " \u00d7", width=80, height=25, fg_color=LIGHT,
                   state="disabled" if self.working else "normal",
                   command=lambda file=path: self.remove_file(file)).pack(anchor="w", padx=3, pady=2)

    def remove_file(self, path):
        self.files.remove(path)
        self.update_files()

    def set_working(self, working):
        self.working = working
        state = "disabled" if working else "normal"
        for widget in (self.attach_button, self.switch, self.send_button, self.input):
            widget.configure(state=state)
        self.send_button.configure(text="处理中..." if working else "发送")
        self.update_files()

    def invoke(self, action, fields, complete, failure=None):
        if self.working:
            return False
        self.show_feedback("")
        backend = self.backend

        def finish(ok, value):
            self.set_working(False)
            if not ok:
                if failure:
                    failure(value)
                else:
                    self.show_feedback(str(value), isinstance(value, SettingsRequired))
                return
            self.remember(value.get("result") or value)
            complete(value)

        self.set_working(True)
        started = self.app.run_task(lambda: backend.run(action, fields), lambda value: finish(True, value),
                                    "正在处理...", lambda error: finish(False, error))
        if not started:
            self.set_working(False)
        return started

    def remember(self, value):
        kind = value["type"]
        if kind == "group_prepare":
            self.context.clear()
        if kind == "group_result":
            self.context.update(group_token=value["token"], schedule_token=None)
        if kind == "schedule":
            self.context.update(group_token=value["group_token"], schedule_token=value["token"])
        if value.get("updated"):
            self.app.refresh_source(quiet=True)

    def append_reply(self, value):
        self.messages.append({"role": "assistant", "mode": self.mode, **value})
        self.messages = self.messages[-48:]
        self.guide_open = False
        self.guide_button.configure(text="使用指引")
        self.render()

    def complete_preview(self, reply, preview, receipt):
        details = [row["after"] for row in preview.get("rows", []) if row.get("after")]
        reply.update(message="\n".join([receipt["message"], *details]), result=receipt)
        reply.pop("preparation", None)
        self.render()

    def send(self):
        text = self.input.get("1.0", "end-1c").strip()
        if not text or self.working:
            return
        if self.mode == "operate" and self.app.dirty:
            self.show_feedback("请先保存桌面课表的当前编辑, 再继续课表操作.")
            return
        files = list(self.files)
        history = [{key: item[key] for key in ("role", "message")}
                   for item in self.messages if item["mode"] == self.mode][-10:]

        def complete(value):
            if value.get("retain"):
                self.show_feedback(value["message"])
                return
            self.messages.append({"role": "user", "mode": self.mode, "message": text,
                                  "attachments": [file.name for file in files]})
            self.input.delete("1.0", "end")
            if not value.get("keep_files"):
                self.files.clear()
                self.update_files()
            self.append_reply(value)

        self.invoke("assistant", {"mode": self.mode, "text": text, "history": history,
                    "files": [{"name": path.name, "path": str(path)} for path in files], **self.context}, complete)

    def choose(self, fields):
        if self.mode == "operate":
            if fields.get("group_token") and fields["group_token"] != self.context.get("group_token"):
                self.show_feedback("组队资料已更新, 请从最新的结果选择.")
                return
            self.invoke("assistant_choose", {"mode": self.mode, **fields}, self.append_reply)

    def open_result(self, reply):
        from .assistant_review import AssistantReview
        value = reply["result"]
        if value["type"] == "todos":
            self.app.go("todos")
        elif value["type"] == "todo_reserve":
            self.app.reserve_todo(value["item"])
        elif value["type"] == "agenda":
            if value.get("week"):
                self.app.review_week = value["week"]
            self.app.go("review")
        else:
            try:
                AssistantReview(self, reply)
            except (ValueError, OSError) as exc:
                messagebox.showerror("无法打开结果", str(exc), parent=self.app)

    def open_current_schedule(self):
        self.invoke("schedule", {"operation": "current", "token": self.context.get("schedule_token")},
                    lambda value: self.open_result({"result": value}))
