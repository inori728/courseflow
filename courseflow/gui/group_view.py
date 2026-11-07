"""Group availability UI, with review before timetable-to-card conversion."""
from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
from urllib.parse import urlencode
import json

import customtkinter as ctk

from .. import service
from ..model import DAYS
from .dialogs import ACCENT, Button, OptionMenu, INK, MUTED, CourseDialog, Modal, SemesterDialog, TextDialog, label
from .styles import LIGHT, LIGHT_ACTIVE, LIGHT_HOVER


def add_member(app, card):
    if any(existing.name == card.name for existing in app.members):
        raise ValueError("成员名称重复, 请为这位成员换一个名称.")
    app.members.append(card)
    app.go("group")


class MemberReviewDialog(Modal):
    def __init__(self, app, timetable, notes=None):
        super().__init__(app, "核对成员课表", 880, 700)
        self.timetable = copy.deepcopy(timetable)
        label(self, "核对后加入组队", 23).pack(anchor="w", padx=24, pady=(22, 6))
        label(self, "求交只使用忙闲格. 导出的忙闲卡不包含课程名称和教室.", 12, MUTED).pack(anchor="w", padx=24, pady=(0, 12))
        form = ctk.CTkFrame(self, fg_color="white", corner_radius=12)
        form.pack(fill="x", padx=24)
        label(form, "成员名称").pack(side="left", padx=(16, 8), pady=14)
        self.name = ctk.CTkEntry(form, width=170)
        self.name.insert(0, f"成员{len(app.members) + 1}")
        self.name.pack(side="left", padx=(0, 18))
        label(form, "校区(可留空)").pack(side="left", padx=(0, 8))
        self.campus = ctk.CTkEntry(form, width=165)
        self.campus.pack(side="left")
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=24, pady=10)
        for text, command in [("新增课程", lambda: CourseDialog(self, self.append_course)),
                              ("编辑所选", self.edit), ("学期与作息", lambda: SemesterDialog(self, self.timetable, self.set_semester))]:
            Button(toolbar, text=text, width=110, height=32, fg_color="#e5ebf8", text_color=ACCENT, command=command).pack(side="left", padx=(0, 8))
        frame = ctk.CTkFrame(self, fg_color="white")
        frame.pack(fill="both", expand=True, padx=24)
        self.tree = ttk.Treeview(frame, columns=("name", "day", "periods", "weeks", "room"), show="headings", height=8)
        for key, title, width in [("name", "课程", 170), ("day", "星期", 65), ("periods", "节次", 65), ("weeks", "周次", 160), ("room", "地点", 150)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=50)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda event: self.edit())
        self.notes = label(self, "\n".join((notes or [])[:4]), 12, MUTED, wraplength=810, justify="left")
        self.notes.pack(anchor="w", padx=24, pady=10)
        self.confirmed = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(self, text="我已核对课程, 周次和学期信息", variable=self.confirmed).pack(anchor="w", padx=24, pady=8)
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=18)
        Button(footer, text="取消", width=90, fg_color="#dfe5f0", text_color=INK, command=self.close).pack(side="left")
        Button(footer, text="确认加入", fg_color=ACCENT, command=self.accept).pack(side="right")
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for index, course in enumerate(self.timetable.courses):
            self.tree.insert("", "end", iid=str(index), values=(course.name, course.day_name, f"{course.start}-{course.end}", course.weeks, course.room))

    def append_course(self, course):
        self.timetable.courses.append(course)
        self.confirmed.set(False)
        self.refresh()

    def edit(self):
        selected = self.tree.selection()
        if not selected:
            return
        index = int(selected[0])
        def save(course):
            self.timetable.courses[index] = course
            self.confirmed.set(False)
            self.refresh()
        CourseDialog(self, save, self.timetable.courses[index])

    def set_semester(self, timetable):
        self.timetable = timetable
        self.confirmed.set(False)

    def accept(self):
        try:
            if not self.confirmed.get():
                raise ValueError("请先核对并勾选确认.")
            card = service.make_busy_card(self.timetable, self.name.get(), campus=self.campus.get())
            add_member(self.app, card)
            self.close()
        except ValueError as exc:
            messagebox.showerror("请核对成员信息", str(exc), parent=self)


class CardConfirmDialog(Modal):
    def __init__(self, app, card):
        super().__init__(app, "导入忙闲卡", 650, 460)
        self.card = card
        label(self, "核对忙闲卡", 23).pack(anchor="w", padx=28, pady=(26, 12))
        weeks = sorted(card.busy)
        label(self, f"学期起始: {card.semester_start.isoformat()}\n提供第 {', '.join(str(w) for w in weeks)} 周忙闲信息\n卡片只包含忙闲格, 不包含课程内容.",
              13, MUTED, wraplength=590, justify="left").pack(anchor="w", padx=28, pady=10)
        label(self, "成员名称").pack(anchor="w", padx=28, pady=(10, 5))
        self.name = ctk.CTkEntry(self, width=590)
        self.name.insert(0, card.name)
        self.name.pack(fill="x", padx=28)
        Button(self, text="确认加入", fg_color=ACCENT, command=self.accept).pack(anchor="e", padx=28, pady=25)

    def accept(self):
        try:
            name = self.name.get().strip()
            if not name or len(name) > 80:
                raise ValueError("请填写 1-80 字的成员名称.")
            add_member(self.app, replace(self.card, name=name))
            self.close()
        except ValueError as exc:
            messagebox.showerror("无法加入", str(exc), parent=self)


class MeetingDialog(Modal):
    def __init__(self, app, result, window):
        super().__init__(app, "导出会议日历", 650, 490)
        self.result, self.window = result, window
        label(self, "选定会议时间", 23).pack(anchor="w", padx=28, pady=(25, 8))
        label(self, f"可选范围: {window.describe()}\n日期以 {result.monday.isoformat()} 起的这一周为准.", 13, MUTED, justify="left").pack(anchor="w", padx=28, pady=(0, 18))
        self.fields = {}
        for key, title, value in [("title", "会议名称", "小组讨论"), ("start", "开始节次", str(window.start)),
                                  ("end", "结束节次", str(min(window.end, window.start + 1)))]:
            label(self, title).pack(anchor="w", padx=28, pady=(7, 3))
            entry = ctk.CTkEntry(self, height=34)
            entry.insert(0, value)
            entry.pack(fill="x", padx=28)
            self.fields[key] = entry
        Button(self, text="选择位置并导出 .ics", fg_color=ACCENT, command=self.export).pack(anchor="e", padx=28, pady=22)

    def export(self):
        try:
            first, last = int(self.fields["start"].get()), int(self.fields["end"].get())
            path = filedialog.asksaveasfilename(parent=self, title="导出会议日历", defaultextension=".ics", initialfile="小组会议.ics", filetypes=[("日历", "*.ics")])
            if not path:
                return
            service.export_group_meeting(self.result, self.window, self.fields["title"].get(), path, first, last)
            messagebox.showinfo("已导出", "会议日历已生成, 可自行分享并导入日历.", parent=self)
            self.close()
        except (ValueError, OSError) as exc:
            messagebox.showerror("导出未完成", str(exc), parent=self)


class GroupView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        app.page_title.configure(text="找出全员空闲的时间")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        left = ctk.CTkScrollableFrame(self, width=260, fg_color="white", corner_radius=14)
        left.grid(row=0, column=0, sticky="ns", padx=(25, 16), pady=22)
        label(left, "组队成员", 19).pack(anchor="w", padx=12, pady=(14, 12))
        for text, callback in [("把当前课表加入", self.add_current), ("添加成员课表文件", self.import_member),
                               ("粘贴忙闲卡短码", self.paste_card), ("打开忙闲卡文件", self.open_card),
                               ("导出我的忙闲卡", self.export_card), ("打开零安装点格页", self.open_grid),
                               ("分享点格页", self.share_grid)]:
            requires_current = text in {"把当前课表加入", "导出我的忙闲卡"}
            state = "disabled" if requires_current and not app.tt.courses else "normal"
            Button(left, text=text, height=32, fg_color=LIGHT, text_color=ACCENT,
                   state=state, command=callback).pack(fill="x", padx=12, pady=4)
        if not app.tt.courses:
            label(left, "当前还没有课表. 可先到导入页准备自己的课表, 或直接添加成员文件 / 忙闲卡.",
                  12, MUTED, wraplength=230, justify="left").pack(anchor="w", padx=12, pady=(10, 0))
        label(left, "已加入的成员", 13, MUTED).pack(anchor="w", padx=12, pady=(22, 8))
        if not app.members:
            label(left, "先添加课表或导入忙闲卡", 12, MUTED, wraplength=220).pack(anchor="w", padx=12)
        for index, card in enumerate(app.members):
            row = ctk.CTkFrame(left, fg_color="#f3f6fc")
            row.pack(fill="x", padx=10, pady=5)
            label(row, f"{card.name}\n{len(card.busy)} 周忙闲信息", 12, INK, justify="left").pack(side="left", padx=10, pady=10)
            Button(row, text="移除", width=52, height=28, fg_color="#e5eaf5", text_color=MUTED,
                         command=lambda i=index: self.remove_member(i)).pack(side="right", padx=8)
        right = ctk.CTkFrame(self, fg_color="white", corner_radius=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 25), pady=22)
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)
        controls = ctk.CTkFrame(right, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", padx=18, pady=15)
        label(controls, "第").pack(side="left")
        self.week = ctk.CTkEntry(controls, width=54)
        self.week.insert(0, "1")
        self.week.pack(side="left", padx=6)
        label(controls, "周 / 至少连续").pack(side="left")
        self.minimum = OptionMenu(controls, values=[str(n) for n in range(1, 7)], width=65, fg_color="#edf1fa", text_color=INK)
        self.minimum.set("2")
        self.minimum.pack(side="left", padx=6)
        label(controls, "节").pack(side="left")
        Button(controls, text="查找空闲", width=100, fg_color=ACCENT,
               state="normal" if app.members else "disabled", command=self.find).pack(side="right")
        self.summary = label(right, "周次按第一位成员的学期计算, 系统按实际日期对齐各成员.", 12, MUTED, wraplength=620, justify="left")
        self.summary.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))
        self.tabs = ctk.CTkTabview(
            right, fg_color="#f3f6fc", text_color=INK,
            segmented_button_fg_color=LIGHT,
            segmented_button_selected_color=LIGHT_ACTIVE,
            segmented_button_selected_hover_color="#bdceff",
            segmented_button_unselected_color=LIGHT,
            segmented_button_unselected_hover_color=LIGHT_HOVER,
        )
        self.tabs.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 12))
        self.tabs.add("全员空闲")
        self.tabs.add("热力图")
        for tab in ("全员空闲", "热力图"):
            label(self.tabs.tab(tab), "1. 左侧添加成员课表或忙闲卡\n2. 选择查询周次和最少连续节数\n3. 点击查找空闲, 查看清单或热力图\n\n只按已提供的信息计算, 未知周次会提示补充.",
                  15, MUTED, justify="left").pack(expand=True, padx=20, pady=30)
        footer = ctk.CTkFrame(right, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        self.export_meeting_button = Button(footer, text="导出所选会议日历", width=165, fg_color=ACCENT, state="disabled", command=self.meeting)
        self.export_meeting_button.pack(side="left", padx=(0, 8))
        self.heatmap_button = Button(footer, text="导出热力图", width=120, fg_color="#edf1fa", text_color=ACCENT, state="disabled", command=self.heatmap)
        self.heatmap_button.pack(side="left")
        self.result = None

    def add_current(self):
        if not self.app.tt.courses:
            messagebox.showinfo("先导入课表", "当前课表没有课程.", parent=self.app)
            return
        MemberReviewDialog(self.app, self.app.tt)

    def import_member(self):
        path = filedialog.askopenfilename(parent=self.app, title="添加成员课表", filetypes=[("课表或图片", "*.yaml *.yml *.xlsx *.csv *.png *.jpg *.jpeg *.webp")])
        if not path:
            return
        try:
            suffix = Path(path).suffix.lower()
            if suffix in {".yaml", ".yml"}:
                MemberReviewDialog(self.app, service.load_timetable(path))
            elif suffix in {".xlsx", ".csv"}:
                courses, notes = service.import_table(path)
                notes.insert(0, "学期与作息暂沿用当前课表, 请核对是否与该成员一致.")
                MemberReviewDialog(self.app, service.member_timetable(courses, self.app.tt), notes)
            elif self.app.ensure_ai():
                basis = copy.deepcopy(self.app.tt)
                self.app.run_task(lambda: service.import_image(path, basis.weeks_total),
                                  lambda draft: MemberReviewDialog(self.app, service.member_timetable(draft.courses, basis),
                                      ["学期与作息暂沿用当前课表, 请核对."] + draft.notes), "正在识别成员课表, 稍后请核对...")
        except (ValueError, OSError) as exc:
            messagebox.showerror("导入未完成", str(exc), parent=self.app)

    def paste_card(self):
        def accept(text, dialog):
            card = service.read_busy_card(text)
            dialog.close()
            CardConfirmDialog(self.app, card)
            return False
        TextDialog(self.app, "粘贴忙闲卡", "粘贴以 CF1. 开头的完整忙闲卡短码.", accept)

    def open_card(self):
        path = filedialog.askopenfilename(parent=self.app, title="导入忙闲卡", filetypes=[("忙闲卡", "*.busycard *.txt")])
        if path:
            try:
                CardConfirmDialog(self.app, service.read_busy_card(Path(path).read_text(encoding="utf-8")))
            except (ValueError, OSError) as exc:
                messagebox.showerror("卡片无法读取", str(exc), parent=self.app)

    def export_card(self):
        def accept(text, dialog):
            week = int(self.week.get())
            card = service.make_busy_card(self.app.tt, text, [week])
            path = filedialog.asksaveasfilename(parent=dialog, title="导出忙闲卡", initialfile=f"第{week}周.busycard", defaultextension=".busycard", filetypes=[("忙闲卡", "*.busycard")])
            if path:
                service.export_busy_card(card, path)
                messagebox.showinfo("已导出", "已导出查询周的忙闲卡, 可自行分享给组长.", parent=dialog)
                return True
            return False
        TextDialog(self.app, "导出我的忙闲卡", "输入你在组队中使用的名称. 只导出左侧查询框指定周次的忙闲格.", accept, button="选择保存位置")

    def open_grid(self):
        page = service.point_grid_path()
        if page.exists():
            try:
                defaults = service.point_grid_defaults(self.app.tt, self.app.members, self.week.get())
                params = {"start": defaults["start"], "week": defaults["week"],
                          "times": json.dumps(defaults["period_times"]), "timezone": defaults["timezone"]}
                webbrowser.open(page.as_uri() + "?" + urlencode(params))
            except ValueError as exc:
                messagebox.showerror("请核对查询信息", str(exc), parent=self.app)
        else:
            messagebox.showerror("页面不存在", "点格页资源未找到, 请检查安装包.", parent=self.app)

    def share_grid(self):
        try:
            defaults = service.point_grid_defaults(self.app.tt, self.app.members, self.week.get())
            week = defaults["week"]
            path = filedialog.asksaveasfilename(
                parent=self.app, title="分享点格页", initialdir=str(self.app.source.parent),
                initialfile=f"CourseFlow-第{week}周点格页.html", defaultextension=".html",
                filetypes=[("点格页 HTML", "*.html")],
            )
            if not path:
                return
            result = service.export_point_grid(path, self.app.tt, self.app.members, week)
            messagebox.showinfo(
                "点格页已保存",
                f"{result}\n\n把这个 HTML 文件发给成员, 对方用浏览器打开并填写.\n"
                "填写后生成忙闲卡文件或短码发回给你, 再导入组队.\n"
                "页面只预填学期日期, 周次和已有作息, 不包含成员姓名或忙碌格.", parent=self.app,
            )
        except (ValueError, OSError) as exc:
            messagebox.showerror("分享点格页未完成", str(exc), parent=self.app)

    def remove_member(self, index):
        if messagebox.askyesno("移除成员", "只从本次组队列表移除这位成员?", parent=self.app):
            del self.app.members[index]
            self.app.go("group")

    def find(self):
        try:
            self.result = service.group_free(self.app.members, int(self.week.get()), int(self.minimum.get()))
            self.app.last_group_result = self.result
            result = self.result
            self.summary.configure(text=f"{result.monday.isoformat()} 起 / {len(result.names)} 位成员\n" + "\n".join(result.warnings + ([result.campus_hint] if result.campus_hint else [])))
            for name in ("全员空闲", "热力图"):
                for child in self.tabs.tab(name).winfo_children():
                    child.destroy()
            panel = ctk.CTkScrollableFrame(self.tabs.tab("全员空闲"), fg_color="transparent")
            panel.pack(fill="both", expand=True)
            self.selected = tk.IntVar(value=0)
            for index, window in enumerate(result.windows):
                ctk.CTkRadioButton(panel, text=window.describe(), variable=self.selected, value=index,
                                   font=("Microsoft YaHei UI", 14)).pack(anchor="w", padx=15, pady=9)
            if not result.windows:
                label(panel, "没有满足条件的全员空闲时段.", 14, MUTED).pack(pady=35)
            grid = ctk.CTkScrollableFrame(self.tabs.tab("热力图"), fg_color="transparent")
            grid.pack(fill="both", expand=True)
            label(grid, "绿色 = 全员空闲; 数字 = 这一节忙碌的人数", 12, MUTED).grid(
                row=0, column=0, columnspan=8, sticky="w", padx=6, pady=(6, 8))
            for day in range(7):
                label(grid, DAYS[day], 11).grid(row=1, column=day + 1, padx=3, pady=8)
            for period in range(1, 13):
                label(grid, str(period), 11, MUTED).grid(row=period + 1, column=0, padx=6)
                for day in range(7):
                    count = result.counts[day * 12 + period - 1]
                    color = "#d9f3e7" if count == 0 else "#dce4f6"
                    ctk.CTkLabel(grid, text="空闲" if not count else f"{count} 人忙", width=58, height=28, fg_color=color,
                                 corner_radius=5, text_color="#31644e" if not count else "#415576", font=("Microsoft YaHei UI", 11)).grid(row=period + 1, column=day + 1, padx=2, pady=2)
            self.export_meeting_button.configure(state="normal" if result.windows else "disabled")
            self.heatmap_button.configure(state="normal")
        except ValueError as exc:
            messagebox.showerror("无法求交", str(exc), parent=self.app)

    def meeting(self):
        if self.result and self.result.windows:
            MeetingDialog(self.app, self.result, self.result.windows[self.selected.get()])

    def heatmap(self):
        path = filedialog.asksaveasfilename(parent=self.app, title="导出忙闲热力图", initialfile="组队忙闲.png", defaultextension=".png", filetypes=[("PNG 图片", "*.png")])
        if path and self.result:
            result = self.result
            self.app.run_task(lambda: service.export_group_heatmap(result, path),
                              lambda saved: messagebox.showinfo("已导出", str(saved), parent=self.app), "正在导出热力图...")
