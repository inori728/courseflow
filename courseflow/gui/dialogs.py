"""Small form dialogs, shared by the desktop views."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from .. import service
from ..model import DAYS
from .styles import ACCENT, BG, INK, MUTED, Button, OptionMenu


class Modal(ctk.CTkToplevel):
    def __init__(self, master, title, width=720, height=560):
        super().__init__(master)
        self.app = getattr(master, "app", master)
        self.title(title)
        screen_width, screen_height = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(width, screen_width - 60), min(height, screen_height - 90)
        x = max(10, min(master.winfo_rootx() + max(0, (master.winfo_width() - width) // 2), screen_width - width - 15))
        y = max(25, min(master.winfo_rooty() + max(0, (master.winfo_height() - height) // 2), screen_height - height - 50))
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min(width, 600), min(height, 450))
        self.configure(fg_color=BG)
        self.transient(master)
        self._previous_grab = self.grab_current()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda event: self.close())
        self.after(80, self._activate)

    def _activate(self):
        if self.winfo_exists():
            self.lift()
            self.grab_set()

    def close(self):
        try:
            self.grab_release()
            if self._previous_grab is not None and self._previous_grab.winfo_exists():
                self._previous_grab.grab_set()
        except tk.TclError:
            pass
        self.destroy()


def label(parent, text, size=14, color=INK, **kwargs):
    return ctk.CTkLabel(parent, text=text, text_color=color, font=("Microsoft YaHei UI", max(size, 13)), **kwargs)


class TextDialog(Modal):
    def __init__(self, master, title, hint, submit, initial="", button="继续"):
        super().__init__(master, title, 760, 540)
        label(self, title, 23).pack(anchor="w", padx=28, pady=(25, 7))
        label(self, hint, 13, MUTED, wraplength=680, justify="left").pack(anchor="w", padx=28, pady=(0, 16))
        self.text = ctk.CTkTextbox(self, font=("Microsoft YaHei UI", 14), border_width=1, border_color="#dce3ef")
        self.text.pack(fill="both", expand=True, padx=28)
        self.text.insert("1.0", initial)
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.pack(fill="x", padx=28, pady=22)
        Button(self.footer, text="取消", width=90, fg_color="#dfe5f0", text_color=INK, command=self.close).pack(side="left")
        self.submit_button = Button(self.footer, text=button, fg_color=ACCENT, command=lambda: self._submit(submit))
        self.submit_button.pack(side="right")
        self.after(120, self.text.focus_set)

    def _submit(self, callback):
        value = self.text.get("1.0", "end-1c").strip()
        if not value:
            messagebox.showinfo("请填写内容", "请先输入或粘贴文字.", parent=self)
            return
        try:
            if callback(value, self):
                self.close()
        except (ValueError, OSError) as exc:
            messagebox.showerror("无法继续", str(exc), parent=self)


class CourseDialog(Modal):
    def __init__(self, master, callback, course=None, wizard=False):
        super().__init__(master, "分步录入" if wizard else "编辑课程", 660, 540)
        self.callback, self.original, self.wizard = callback, course, wizard
        label(self, "把这一门课填完整", 23).pack(anchor="w", padx=28, pady=(25, 8))
        label(self, "周次示例: 1-16周 / 1-16周(单) / 1-4,6,8-10周", 12, MUTED).pack(anchor="w", padx=28, pady=(0, 15))
        form = ctk.CTkFrame(self, fg_color="white", corner_radius=14)
        form.pack(fill="both", expand=True, padx=28)
        form.grid_columnconfigure(1, weight=1)
        defaults = {
            "name": course.name if course else "", "day": course.day_name if course else DAYS[0],
            "periods": f"{course.start}-{course.end}" if course else "1-2",
            "weeks": course.weeks if course else "1-16周", "room": course.room if course else "",
        }
        self.entries = {}
        for row, (key, title) in enumerate([("name", "课程名称"), ("day", "星期"), ("periods", "节次"), ("weeks", "周次"), ("room", "地点")]):
            label(form, title).grid(row=row, column=0, sticky="w", padx=20, pady=10)
            widget = OptionMenu(form, values=DAYS, fg_color="#edf1fa", text_color=INK) if key == "day" else ctk.CTkEntry(form, height=36)
            if key == "day":
                widget.set(defaults[key])
            else:
                widget.insert(0, defaults[key])
            widget.grid(row=row, column=1, sticky="ew", padx=20, pady=10)
            self.entries[key] = widget
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=28, pady=22)
        Button(footer, text="取消", width=90, fg_color="#dfe5f0", text_color=INK, command=self.close).pack(side="left")
        if wizard:
            Button(footer, text="保存并继续录入", fg_color=ACCENT, command=lambda: self.save(True)).pack(side="right", padx=(10, 0))
        Button(footer, text="保存这一门", fg_color=ACCENT, command=self.save).pack(side="right")

    def save(self, again=False):
        try:
            values = {key: widget.get() for key, widget in self.entries.items()}
            course = service.course_from_fields(**values, original=self.original)
            self.callback(course)
            if again:
                self.entries["name"].delete(0, "end")
                self.entries["room"].delete(0, "end")
                self.entries["name"].focus_set()
            else:
                self.close()
        except ValueError as exc:
            messagebox.showerror("请核对课程", str(exc), parent=self)


class SemesterDialog(Modal):
    def __init__(self, master, tt, callback):
        super().__init__(master, "学期与作息", 820, 690)
        self.tt, self.callback = tt, callback
        label(self, "学期与作息", 23).pack(anchor="w", padx=28, pady=(24, 5))
        label(self, "日期用于周次换算; 作息用于日历和通知中的钟点转换. 请按学校实际安排填写.", 12, MUTED, wraplength=750).pack(anchor="w", padx=28, pady=(0, 14))
        body = ctk.CTkScrollableFrame(self, fg_color="white", corner_radius=14)
        body.pack(fill="both", expand=True, padx=28)
        body.grid_columnconfigure(1, weight=1)
        self.fields = {}
        rows = [("term", "学期名称", tt.term), ("start", "第1周周一", tt.semester_start.isoformat() if tt.semester_start else ""),
                ("total", "学期总周数", str(tt.weeks_total)), ("timezone", "时区", tt.timezone)]
        for row, (key, title, value) in enumerate(rows):
            label(body, title).grid(row=row, column=0, padx=18, pady=7, sticky="w")
            entry = ctk.CTkEntry(body, height=34, placeholder_text="YYYY-MM-DD" if key == "start" else "")
            if value:
                entry.insert(0, value)
            entry.grid(row=row, column=1, padx=18, pady=7, sticky="ew")
            self.fields[key] = entry
        label(body, "节次时间, 格式 HH:MM-HH:MM", 14).grid(row=4, column=0, columnspan=2, padx=18, pady=(16, 8), sticky="w")
        self.clocks = {}
        for period in range(1, 13):
            label(body, f"第 {period} 节").grid(row=period + 4, column=0, padx=18, pady=4, sticky="w")
            entry = ctk.CTkEntry(body, height=30, placeholder_text="08:00-08:45")
            if period in tt.period_times:
                a, b = tt.period_times[period]
                entry.insert(0, f"{a.strftime('%H:%M')}-{b.strftime('%H:%M')}")
            entry.grid(row=period + 4, column=1, padx=18, pady=4, sticky="ew")
            self.clocks[period] = entry
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=28, pady=20)
        Button(footer, text="取消", width=90, fg_color="#dfe5f0", text_color=INK, command=self.close).pack(side="left")
        Button(footer, text="确认设置", fg_color=ACCENT, command=self.save).pack(side="right")

    def save(self):
        try:
            values = {key: entry.get() for key, entry in self.fields.items()}
            updated = service.configure_semester(self.tt, clocks={p: entry.get() for p, entry in self.clocks.items()}, **values)
            self.callback(updated)
            self.close()
        except ValueError as exc:
            messagebox.showerror("请核对设置", str(exc), parent=self)
