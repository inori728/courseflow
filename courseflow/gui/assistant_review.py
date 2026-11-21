"""Desktop review forms for the shared assistant workbench."""
from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from PIL import Image

from ..harness import _semester_data
from ..model import DAYS
from ..source import timetable_from_mapping, timetable_mapping
from .dialogs import ACCENT, Button, CourseDialog, INK, LIGHT, MUTED, Modal, OptionMenu, SemesterDialog, label
from .group_schedule import ScheduleCardPreview, ScheduleFields, _summary


class TableReview(ctk.CTkFrame):
    def __init__(self, master, dialog, timetable, editable):
        super().__init__(master, fg_color="transparent")
        self.dialog, self.tt = dialog, timetable
        self.originals = list(range(len(timetable.courses)))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(2, 5))
        Button(bar, text="学期与作息", fg_color=LIGHT, command=self.semester).pack(side="left")
        if editable:
            Button(bar, text="编辑所选", fg_color=LIGHT, command=self.course).pack(side="left", padx=5)
            Button(bar, text="新增课程", fg_color=LIGHT, command=lambda: self.course(False)).pack(side="left")
            Button(bar, text="移除所选", fg_color=LIGHT, command=self.remove).pack(side="left", padx=5)
        self.heading = label(self, "", 13, MUTED)
        self.heading.pack(anchor="w", pady=4)
        table = ctk.CTkFrame(self, fg_color="transparent")
        table.pack(fill="x")
        table.grid_columnconfigure(0, weight=1)
        columns = ("name", "day", "periods", "weeks", "room")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", height=9, selectmode="browse")
        for key, title, width in zip(columns, ("课程", "星期", "节次", "周次", "地点"), (190, 72, 72, 125, 140)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=60)
        self.tree.grid(row=0, column=0, sticky="ew")
        vertical = ttk.Scrollbar(table, command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vertical.set)
        if editable:
            self.tree.bind("<Double-1>", lambda event: self.course())
        self.refresh()

    def refresh(self):
        self.heading.configure(text=f"{self.tt.term or '学期未命名'} / {self.tt.semester_start or '待核对第 1 周周一'} / {len(self.tt.courses)} 门课")
        self.tree.delete(*self.tree.get_children())
        for row, item in enumerate(self.tt.courses):
            self.tree.insert("", "end", iid=str(row), values=(
                item.name, item.day_name, f"{item.start}-{item.end}", item.weeks, item.room))

    def semester(self):
        def change(tt):
            self.tt = tt
            self.refresh()
        SemesterDialog(self.dialog, self.tt, change)

    def course(self, selected=True):
        selection = self.tree.selection()
        if selected and not selection:
            return
        index = int(selection[0]) if selected else None

        def change(course):
            if index is None:
                self.tt.courses.append(course)
                self.originals.append(None)
            else:
                self.tt.courses[index] = course
            self.refresh()

        CourseDialog(self.dialog, change, self.tt.courses[index] if index is not None else None)

    def remove(self):
        if self.tree.selection():
            index = int(self.tree.selection()[0])
            del self.tt.courses[index], self.originals[index]
            self.refresh()

    def values(self):
        return {"semester": _semester_data(self.tt), "courses": [
            {"name": course.name, "day": course.day_name, "periods": f"{course.start}-{course.end}",
             "weeks": course.weeks, "room": course.room, "index": original}
            for course, original in zip(self.tt.courses, self.originals)]}


class AssistantReview(Modal):
    def __init__(self, view, reply):
        super().__init__(view.app, "核对助手结果", 960, 720)
        self.view, self.backend = view, view.backend
        self.reply = reply
        self.preparation = reply.get("preparation")
        self.edits = {}
        self.heading = label(self, "", 22)
        self.heading.pack(anchor="w", padx=22, pady=(12, 5))
        self.body = ctk.CTkScrollableFrame(self, fg_color="white")
        self.body.pack(fill="both", expand=True, padx=21, pady=4)
        self.status = label(self, "", 13, MUTED, justify="left", wraplength=840)
        self.status.pack(anchor="w", padx=22, pady=(4, 0))
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.pack(fill="x", padx=21, pady=(5, 13))
        self.render(reply["result"], reply.get("preferred_day"))

    def render(self, value, preferred_day=None):
        self.value = value
        self.preferred_day = preferred_day
        for frame in (self.body, self.footer):
            for child in frame.winfo_children():
                child.destroy()
        self.status.configure(text="")
        back = self.close
        if value["type"] == "preview" and self.preparation and self.preparation["token"] == value["token"] and self.edits:
            back = lambda: self.render(self.preparation)
        Button(self.footer, text="返回", fg_color=LIGHT, command=back).pack(side="left")
        handler = getattr(self, "show_" + value["type"], None)
        if handler is None:
            self.heading.configure(text="助手结果")
            self.note(value.get("message") or "请在常用功能中查看结果.")
        else:
            handler(value)

    def note(self, text, muted=False):
        if text:
            label(self.body, text, 14, MUTED if muted else INK, wraplength=790,
                  justify="left").pack(anchor="w", padx=12, pady=5)

    def primary(self, text, command):
        Button(self.footer, text=text, command=command).pack(side="right", padx=(8, 0))

    def submit(self, action, fields, complete=None):
        preview = self.value

        def display(value):
            if action == "commit" and value["type"] == "saved":
                self.view.complete_preview(self.reply, preview, value)
            if self.winfo_exists():
                (complete or self.render)(value)

        def failed(exc):
            if self.winfo_exists():
                self.status.configure(text=str(exc))

        self.view.invoke(action, fields, display, failed)

    def table(self, record, editable):
        table = TableReview(self.body, self, timetable_from_mapping(record), editable)
        table.pack(fill="x", padx=12, pady=8)
        return table

    def show_prepare(self, value):
        self.heading.configure(text="核对导入课表")
        self.preparation = value
        record = self.backend._get_draft(value["token"], "change")
        timetable = self.backend._edited(timetable_from_mapping(record["data"]), record["editable"], self.edits)
        table = self.table(timetable_mapping(timetable, sorted_courses=False), record["editable"])
        if record["editable"] and self.edits.get("courses"):
            table.originals = [row["index"] for row in self.edits["courses"]]
        self.note("\n".join(value["table"]["warnings"]), muted=True)

        def preview():
            self.edits = table.values()
            self.submit("preview", {"token": value["token"], **self.edits})
        self.primary("预览导入", preview)

    def show_preview(self, value):
        operation = value.get("write_label") or ("调课" if value["change"] else "导入" if value["overwrite"] else "导出")
        self.heading.configure(text=f"{operation}预览")
        self.note(f"课表 {value['source']}")
        if self.preparation and value["overwrite"] and not value["change"] and not value.get("write_label"):
            self.note(f"将保存 {len(self.edits.get('courses', self.preparation['table']['courses']))} 门课到当前课表.")
        for row in value["rows"]:
            self.note(f"{row['before']} -> {row['after']}" if row["before"] else row["after"])
        self.note("\n".join(value.get("conflicts", []) + value.get("warnings", []) + value.get("notes", [])), muted=True)
        candidates = value.get("candidates", [])
        if candidates:
            selections = {}
            for item in candidates:
                state = tk.BooleanVar(value=item["id"] in value.get("selected", []))
                selections[item["id"]] = state
                ctk.CTkCheckBox(self.body, text=item["label"], variable=state).pack(anchor="w", padx=12, pady=4)
            Button(self.footer, text="预览所选课次", fg_color=LIGHT, command=lambda: self.submit(
                "preview", {"token": value["token"], **self.edits,
                            "selected": [key for key, state in selections.items() if state.get()]})).pack(side="left", padx=8)
        for fmt, encoded in value.get("wallpaper_previews", {}).items():
            self.note("电脑壁纸" if fmt == "desktop" else "手机壁纸")
            with Image.open(BytesIO(base64.b64decode(encoded))) as image:
                image.thumbnail((735, 520), Image.Resampling.LANCZOS)
                preview = ctk.CTkImage(image.copy(), size=image.size)
            ctk.CTkLabel(self.body, text="", image=preview).pack(padx=12, pady=8)
        if value.get("confirmation"):
            def save():
                if value["overwrite"] and self.app.dirty:
                    self.status.configure(text="请先保存桌面课表的当前编辑, 再重新预览.")
                    return
                self.submit("commit", {"token": value["confirmation"]})
            self.primary(f"确认{operation}", save)

    def show_group_prepare(self, value):
        self.heading.configure(text="核对组队资料")
        self.note(value.get("warning"))
        record = self.backend._get_draft(value["token"], "group")
        members = []
        for index, (row, item) in enumerate(zip(value["members"], record["members"]), 1):
            self.note(f"成员 {index}")
            name = ctk.CTkEntry(self.body)
            name.insert(0, row["name"])
            name.pack(fill="x", padx=12, pady=3)
            table = self.table(item["timetable"], item["editable"]) if "timetable" in item else None
            if table is None:
                self.note("忙闲卡周次 " + ", ".join(map(str, row["weeks"])), muted=True)
            self.note("\n".join(row.get("warnings", [])), muted=True)
            members.append((name, table))
        controls = ctk.CTkFrame(self.body, fg_color="transparent")
        controls.pack(fill="x", padx=12, pady=9)
        label(controls, "查询第几周").pack(side="left")
        week = ctk.CTkEntry(controls, width=55)
        week.insert(0, str(value["week"]))
        week.pack(side="left", padx=6)
        label(controls, "至少连续").pack(side="left")
        minimum = ctk.CTkEntry(controls, width=60)
        minimum.insert(0, str(value["minutes"] or value["minimum"]))
        minimum.pack(side="left", padx=6)
        unit = OptionMenu(controls, width=75, values=["分钟", "小节"])
        unit.set("分钟" if value["minutes"] else "小节")
        unit.pack(side="left")
        own = tk.BooleanVar(value=value["include_self"])
        if value["can_include_self"]:
            ctk.CTkCheckBox(controls, text="包含我的课表", variable=own).pack(side="left", padx=10)

        def search():
            try:
                length = int(minimum.get())
                if length <= 0:
                    raise ValueError("invalid group minimum")
                fields = {"token": value["token"], "week": int(week.get()), "include_self": own.get(),
                          "minimum": 1 if unit.get() == "分钟" else length, "minutes": length if unit.get() == "分钟" else 0,
                          "members": [{"name": name.get(), **(table.values() if table else {})} for name, table in members]}
            except ValueError:
                self.status.configure(text="请填写有效周次和时长.")
                return

            def complete(reply):
                self.view.append_reply(reply)
                self.close()

            self.submit("assistant_choose", {"mode": "operate", "review": fields, "preferred_day": self.preferred_day}, complete)
        self.primary("查询共同空档", search)

    def show_group_result(self, value):
        self.heading.configure(text=f"第 {value['week']} 周忙闲图")
        self.note(" / ".join(value["names"]), muted=True)
        self.note("\n".join(value["warnings"]), muted=True)
        grid = ctk.CTkFrame(self.body, fg_color="transparent")
        grid.pack(fill="x", padx=12, pady=5)
        for day, title in enumerate(DAYS):
            grid.grid_columnconfigure(day + 1, weight=1)
            label(grid, title).grid(row=0, column=day + 1, pady=3)
        for period in range(1, 13):
            clock = value["clocks"].get(str(period))
            label(grid, f"{period}  {clock or ''}", 13, MUTED).grid(row=period, column=0, padx=4, pady=3)
            for day in range(7):
                count = value["counts"][day * 12 + period - 1]
                if count:
                    cell = label(grid, f"{count} 人忙", 13, MUTED)
                else:
                    cell = Button(grid, text="空闲", width=68, height=26, fg_color="#d9f3e7",
                                  command=lambda d=day, p=period: self.submit("activity_preview", {
                                      "group_token": value["token"], "day": d, "start": p, "end": p,
                                      "prefer_pair": True, "open_schedule": True}))
                cell.grid(row=period, column=day + 1, padx=3, pady=3)

    def show_activity(self, value):
        self.heading.configure(text="核对选定时段")
        self.note(value["label"])
        if value["needs_clocks"] or value["edit_clocks"]:
            entries = {}
            for period in range(value["fields"]["start"], value["fields"]["end"] + 1):
                key = str(period)
                self.note(f"第 {period} 节 (HH:MM-HH:MM)")
                entry = ctk.CTkEntry(self.body)
                entry.insert(0, value["clocks"].get(key, ""))
                entry.pack(fill="x", padx=12)
                entries[key] = entry
            self.primary("核对作息", lambda: self.submit("activity_clocks", {
                "slot": value["token"], "clocks": {key: entry.get() for key, entry in entries.items()}}))
            return
        title = ctk.CTkEntry(self.body, placeholder_text="活动名称")
        title.insert(0, (value.get("task") or {}).get("title", ""))
        title.pack(fill="x", padx=12, pady=5)
        room = ctk.CTkEntry(self.body, placeholder_text="地点 (选填)")
        room.pack(fill="x", padx=12, pady=5)

        def save():
            if self.app.dirty:
                self.status.configure(text="请先保存桌面课表的当前编辑, 再重新核对.")
                return
            self.submit("activity", {"slot": value["token"], "title": title.get(), "room": room.get()})
        self.primary("确认写入课表", save)

    def checked(self, draft, required=False):
        record = self.backend._get_draft(self.value["token"], "schedule")
        return self.backend.planning._validate(record, draft, required)

    def show_schedule(self, value):
        self.heading.configure(text="核对小组日程")
        review = value.get("review")
        if review:
            self.note("修改前\n" + _summary(value["draft"]), muted=True)
            self.note(review.get("summary"))
        fields = ScheduleFields(self.body, review["draft"] if review else value["draft"])
        fields.pack(fill="x", padx=12, pady=7)

        def preview():
            try:
                draft = fields.values()
                if review:
                    self.submit("schedule", {"operation": "apply", "token": value["token"], "draft": draft},
                                lambda updated: self.preview_schedule(updated))
                else:
                    self.submit("schedule", {"operation": "save", "token": value["token"], "draft": draft},
                                lambda updated: self.preview_schedule(updated))
            except ValueError as exc:
                self.status.configure(text=str(exc))
        self.primary("应用并预览日程卡" if review else "预览日程卡", preview)
        if review:
            Button(self.footer, text="取消修改", fg_color=LIGHT, command=lambda: self.submit(
                "schedule", {"operation": "discard", "token": value["token"]})).pack(side="left", padx=7)

    def preview_schedule(self, value):
        self.render(value)
        try:
            ScheduleCardPreview(self, self.checked(value["draft"], required=True))
        except ValueError as exc:
            self.status.configure(text=str(exc))

    def show_saved(self, value):
        self.heading.configure(text="操作已完成")
        self.note(value.get("message"))
        for file in value["files"]:
            Button(self.body, text=f"另存 {file['name']}", fg_color=LIGHT,
                   command=lambda item=file: self.save_file(item)).pack(anchor="w", padx=12, pady=5)

    def save_file(self, file):
        origin = (self.backend.exports / file["id"]).resolve()
        if not origin.is_relative_to(self.backend.exports.resolve()):
            raise ValueError("请选择本地导出目录中的文件.")
        target = filedialog.asksaveasfilename(parent=self, title="另存导出文件", initialfile=file["name"],
                                              defaultextension=Path(file["name"]).suffix)
        if target:
            try:
                shutil.copyfile(origin, target)
                self.status.configure(text="已保存.")
            except OSError as exc:
                messagebox.showerror("另存未完成", str(exc), parent=self)
