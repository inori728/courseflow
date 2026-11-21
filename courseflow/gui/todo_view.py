"""Desktop access to the same local to-do list as the Harness pane."""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from ..todos import todo_list
from .dialogs import Button, INK, LIGHT, MUTED, label


class TodoView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        form = ctk.CTkFrame(self, fg_color="white", corner_radius=12)
        form.pack(fill="x", pady=(0, 12))
        form.grid_columnconfigure(0, weight=2)
        for column in (1, 2):
            form.grid_columnconfigure(column, weight=1)
        self.fields = {}
        for column, (name, title, hint) in enumerate((
            ("title", "任务名称", ""), ("due", "截止日期 (选填)", "YYYY-MM-DD"),
            ("course", "关联课程 (选填)", ""),
        )):
            label(form, title, 13, MUTED).grid(row=0, column=column, padx=12, pady=(10, 4), sticky="w")
            entry = ctk.CTkEntry(form, placeholder_text=hint or None)
            entry.grid(row=1, column=column, padx=12, pady=(0, 12), sticky="ew")
            self.fields[name] = entry
        Button(form, text="添加待办", width=100, command=self.add).grid(row=1, column=3, padx=8, pady=(0, 12))
        Button(form, text="刷新", width=65, fg_color=LIGHT, command=self.refresh).grid(row=1, column=4, padx=(0, 12), pady=(0, 12))
        self.status = label(self, "", 13, MUTED)
        self.status.pack(anchor="w", pady=(0, 7))
        self.rows = ctk.CTkScrollableFrame(self, fg_color="white")
        self.rows.pack(fill="both", expand=True)
        self.refresh()

    def add(self):
        if self.refresh({"operation": "add", **{key: widget.get() for key, widget in self.fields.items()}}):
            for widget in self.fields.values():
                widget.delete(0, "end")

    def refresh(self, fields=None):
        try:
            result = todo_list(fields or {})
        except (ValueError, OSError) as exc:
            self.status.configure(text=str(exc), text_color="#a13b32")
            return False
        self.status.configure(text=result.get("message") or "选中表示完成. 取消选中可重新打开.", text_color=MUTED)
        for child in self.rows.winfo_children():
            child.destroy()
        if not result["items"]:
            label(self.rows, "还没有待办.", 14, MUTED).pack(anchor="w", padx=12, pady=14)
        for item in result["items"]:
            row = ctk.CTkFrame(self.rows, fg_color=LIGHT, corner_radius=8)
            row.pack(fill="x", padx=6, pady=5)
            state = tk.BooleanVar(value=bool(item.get("done")))
            check = ctk.CTkCheckBox(row, text=item["title"], variable=state, text_color=INK,
                                    command=lambda task=item, done=state: self.set_done(task, done))
            check.pack(side="left", padx=12, pady=10)
            parts = [f"截止 {item['due']}" if item.get("due") else "", item.get("course")]
            label(row, " / ".join(filter(None, parts)), 13, MUTED).pack(side="left", padx=7)
            Button(row, text="删除", width=54, fg_color="white", command=lambda task=item: self.refresh(
                {"operation": "remove", "id": task["id"]})).pack(side="right", padx=7, pady=6)
            if not item.get("done"):
                Button(row, text="留出时间", width=84, fg_color="white",
                       command=lambda task=item: self.app.reserve_todo(task)).pack(side="right", padx=4)
        return True

    def set_done(self, item, state):
        if not self.refresh({"operation": "complete", "id": item["id"], "done": state.get()}):
            state.set(bool(item.get("done")))
