"""Three-step desktop workflow, with optional notification and group views."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
from PIL import Image

from .. import __version__, service
from ..model import Timetable
from ..settings import AI_REQUIRED
from .ai_dialog import AISettingsDialog
from .calendar_view import WeeklyTimetable
from .dialogs import ACCENT, Button, OptionMenu, BG, INK, MUTED, CourseDialog, SemesterDialog, TextDialog, label
from .styles import LIGHT, LIGHT_ACTIVE, LIGHT_HOVER, apply_theme


class CourseFlowApp(ctk.CTk):
    def __init__(self, source=None):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        apply_theme()
        super().__init__()
        self.app = self
        self.title("CourseFlow / 课程流")
        self.geometry("1280x840")
        self.minsize(1040, 680)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        icon = Path(__file__).resolve().parents[1] / "data" / "icon.ico"
        if icon.exists():
            self.after(250, lambda: self.iconbitmap(str(icon)))
        self.tt = Timetable()
        self.source = Path(source) if source else service.default_gui_source()
        self.saved_signature = service.file_signature(self.source)
        self.dirty = False
        self.undo_stack = []
        self.notes = []
        self.review_week = None
        self.review_period = None
        self.review_tab = "周课表"
        self.review_details_open = False
        self._busy = False
        self._closing = False
        self._results = queue.Queue()
        self._preview_image = None
        self.last_group_result = None
        self.members = []
        self.notice_available = importlib.util.find_spec("courseflow.notice") is not None
        self.group_available = importlib.util.find_spec("courseflow.group") is not None
        self.poster_available = importlib.util.find_spec("courseflow.poster") is not None
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._sidebar()
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)
        self.header = ctk.CTkFrame(self.content, fg_color="white", corner_radius=0, height=105)
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)
        self.page_title = label(self.header, "把课表变成每天看得见的东西", 25)
        self.page_title.grid(row=0, column=0, sticky="w", padx=30, pady=(22, 3))
        self.file_label = label(self.header, "", 12, MUTED)
        self.file_label.grid(row=1, column=0, sticky="w", padx=30, pady=(0, 18))
        buttons = ctk.CTkFrame(self.header, fg_color="transparent")
        buttons.grid(row=0, column=1, rowspan=2, padx=25)
        Button(buttons, text="打开课表", width=96, fg_color="#edf1fa", text_color=INK, command=self.open_source).pack(side="left", padx=5)
        Button(buttons, text="保存当前课表", width=110, fg_color=ACCENT, command=self.save).pack(side="left", padx=5)
        Button(buttons, text="另存为", width=80, fg_color=LIGHT, text_color=INK, command=lambda: self.save(as_new=True)).pack(side="left", padx=5)
        self.body = ctk.CTkFrame(self.content, fg_color=BG, corner_radius=0)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.status = label(self.content, "就绪 / 数据保存在本机, AI 仅在你使用相应功能时连接", 12, MUTED, anchor="w")
        self.status.grid(row=3, column=0, sticky="ew", padx=28, pady=(7, 12))
        self.progress = ctk.CTkProgressBar(self.content, height=3, progress_color=ACCENT, mode="indeterminate")
        self.progress.grid(row=2, column=0, sticky="ew")
        self.progress.set(0)
        if self.source.exists():
            try:
                self.tt = service.load_timetable(self.source)
            except ValueError as exc:
                self.after(150, lambda text=str(exc): messagebox.showerror("课表未能打开", text, parent=self))
        self.go("review" if self.tt.courses else "import")
        self._refresh_file_label()
        self.after(80, self._poll)
        self.bind("<Control-s>", lambda event: self.save())
        self.bind("<Control-o>", lambda event: self.open_source())
        self.bind("<Control-z>", lambda event: self.undo())

    def _sidebar(self):
        sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#18233d")
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(9, weight=1)
        logo = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo.grid(row=0, column=0, sticky="ew", padx=22, pady=(32, 22))
        ctk.CTkLabel(logo, text="CF", width=45, height=45, corner_radius=12, fg_color=ACCENT,
                     font=("Segoe UI", 20, "bold"), text_color="white").pack(side="left", padx=(0, 10))
        ctk.CTkLabel(logo, text="CourseFlow", font=("Segoe UI", 20, "bold"), text_color="white").pack(side="left")
        ctk.CTkLabel(sidebar, text="课表在手, 每天有序", font=("Microsoft YaHei UI", 12), text_color="#a3b1ce").grid(row=1, column=0, sticky="w", padx=25, pady=(0, 28))
        self.nav = {}
        items = [("import", "01   导入课表"), ("review", "02   我的课表"), ("export", "03   生成与导出")]
        if self.group_available:
            items.append(("group", "组队 / 找共同空闲"))
        for row, (key, text) in enumerate(items, 2):
            button = Button(sidebar, text=text, anchor="w", height=43, corner_radius=10,
                                   fg_color="transparent", hover_color="#293a5c", text_color="#c8d3e9",
                                   font=("Microsoft YaHei UI", 14), command=lambda page=key: self.go(page))
            button.grid(row=row, column=0, sticky="ew", padx=15, pady=5)
            self.nav[key] = button
        if self.notice_available:
            Button(sidebar, text="调课 / 停课", anchor="w", height=42, fg_color="#283755", hover_color="#34496f",
                         command=self.open_notice).grid(row=7, column=0, sticky="ew", padx=15, pady=(22, 5))
        Button(sidebar, text="AI 接口设置", anchor="w", height=42, fg_color="transparent", hover_color="#293a5c",
                     command=lambda: AISettingsDialog(self)).grid(row=8, column=0, sticky="ew", padx=15, pady=5)
        ctk.CTkLabel(sidebar, text=f"v{__version__}\n本地课表 / 按需连接 AI", text_color="#8293b4", justify="left",
                     font=("Microsoft YaHei UI", 11)).grid(row=10, column=0, sticky="w", padx=25, pady=24)

    def _refresh_file_label(self):
        state = "有修改待保存" if self.dirty else ("已打开" if self.source.exists() else "新课表尚未保存")
        self.file_label.configure(text=f"{self.source.name}  /  {len(self.tt.courses)} 条课程  /  {state}")

    def go(self, page):
        self.page = page
        for key, button in self.nav.items():
            button.configure(fg_color=ACCENT if key == page else "transparent", text_color="white" if key == page else "#c8d3e9")
        for child in self.body.winfo_children():
            child.destroy()
        if page == "import":
            self.show_import()
        elif page == "review":
            self.show_review()
        elif page == "export":
            self.show_export()
        elif page == "group":
            from .group_view import GroupView
            view = GroupView(self.body, self)
            view.pack(fill="both", expand=True)
        self._refresh_file_label()

    def set_timetable(self, tt, notes=None, remember=True):
        if remember:
            self.undo_stack.append(copy.deepcopy(self.tt))
            self.undo_stack = self.undo_stack[-20:]
        self.tt = tt
        self.notes = list(notes or [])
        self.dirty = True
        self._refresh_file_label()

    def undo(self):
        if self.undo_stack:
            self.tt = self.undo_stack.pop()
            self.dirty = True
            self.go(self.page)
            self.status.configure(text="已撤销上一次课表修改, 保存后写回文件.")

    def show_import(self):
        self.page_title.configure(text="从你手上的课表开始")
        area = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        area.pack(fill="both", expand=True, padx=24, pady=20)
        area.grid_columnconfigure((0, 1), weight=1, uniform="cards")
        label(area, "选择一种导入方式", 19).grid(row=0, column=0, columnspan=2, sticky="w", padx=5, pady=(0, 12))
        cards = [
            ("Excel / 文件", "导入 Excel, CSV 或文字课表, 支持学校格式适配配置.", "选择文件", self.import_file),
            ("复制与粘贴", "从教务系统或 Excel 复制表格, 粘贴后预览校对.", "粘贴课表", self.paste_table),
            ("截图识别", "需要具备多模态能力的 AI. 识别结果先校对, 确认后保存.", "选择课表图片", self.import_image),
            ("手动编辑", "从现有课表开始修改, 或添加课程. 停课调课可单独处理.", "打开课程编辑", self.show_course_list),
            ("分步录入", "没有电子课表也可以, 每次填写一门课, 不使用 AI.", "开始录入", lambda: CourseDialog(self, self.add_course, wizard=True)),
            ("先体验一下", "加载内置示例, 试试壁纸, 日历和本周视图. 保存前不会覆盖文件.", "加载示例课表", self.load_demo),
        ]
        for index, (title, hint, action, callback) in enumerate(cards):
            card = ctk.CTkFrame(area, fg_color="white", corner_radius=16, border_width=1, border_color="#e5eaf4")
            card.grid(row=index // 2 + 1, column=index % 2, sticky="nsew", padx=6, pady=7)
            label(card, title, 19).pack(anchor="w", padx=22, pady=(17, 5))
            label(card, hint, 12, MUTED, wraplength=360, justify="left").pack(anchor="w", padx=22, pady=(0, 12))
            Button(card, text=action, height=32, width=150, fg_color=ACCENT if index == 0 else "#edf1fa",
                         text_color="white" if index == 0 else ACCENT, command=callback).pack(anchor="w", padx=22, pady=(0, 18))
        guide = ctk.CTkFrame(area, fg_color="#e9eefc", corner_radius=12)
        guide.grid(row=4, column=0, columnspan=2, sticky="ew", padx=6, pady=(15, 8))
        label(guide, "不确定选哪个? 有 Excel 就选文件; 能复制表格就粘贴; 只有截图再使用识图.", 12, "#4d5f88", wraplength=780, justify="left").pack(anchor="w", padx=20, pady=15)

    def confirm_replace_draft(self):
        return not self.dirty or messagebox.askyesno("替换当前预览", "当前有尚未保存的修改, 是否替换为新的导入结果? 可使用撤销恢复.", parent=self)

    def accept_import(self, courses, notes=None):
        merged = service.merge_import(courses, self.tt)
        self.set_timetable(merged, notes)
        self.review_tab, self.review_week = "周课表", None
        self.go("review")

    def import_file(self):
        path = filedialog.askopenfilename(parent=self, title="选择课表文件", filetypes=[("课表文件", "*.xlsx *.xlsm *.csv *.yaml *.yml *.txt *.tsv *.docx *.pdf"), ("所有文件", "*.*")])
        if not path or not self.confirm_replace_draft():
            return
        try:
            suffix = Path(path).suffix.lower()
            if suffix in {".yaml", ".yml"}:
                self.set_timetable(service.load_timetable(path))
                self.go("review")
                return
            if suffix in {".txt", ".tsv", ".docx", ".pdf"}:
                courses, notes = service.import_document(path)
            else:
                try:
                    courses, notes = service.import_table(path)
                except ValueError:
                    if not messagebox.askyesno("需要格式适配", "自动解析未成功. 是否选择学校格式适配配置?", parent=self):
                        raise
                    adapter = filedialog.askopenfilename(parent=self, title="选择适配配置", filetypes=[("YAML 配置", "*.yaml *.yml")])
                    if not adapter:
                        return
                    courses, notes = service.import_table(path, service.load_adapter(adapter))
            self.accept_import(courses, notes)
        except (OSError, ValueError) as exc:
            messagebox.showerror("导入未完成", str(exc), parent=self)

    def paste_table(self):
        if not self.confirm_replace_draft():
            return
        try:
            initial = self.clipboard_get()
        except tk.TclError:
            initial = ""
        def accept(text, dialog):
            courses, notes = service.import_text(text)
            self.accept_import(courses, notes)
            return True
        TextDialog(self, "粘贴课表", "请粘贴包含星期表头和节次列的表格文字, 下一步可以逐条校对.", accept, initial)

    def ensure_ai(self):
        try:
            service.ai_settings().validate()
            return True
        except ValueError:
            if messagebox.askyesno("需要连接多模态 AI", AI_REQUIRED + "\n\n现在去配置吗?", parent=self):
                AISettingsDialog(self)
            return False

    def import_image(self):
        if not self.ensure_ai():
            return
        path = filedialog.askopenfilename(parent=self, title="选择课表图片", filetypes=[("图片", "*.png *.jpg *.jpeg *.webp *.bmp")])
        if not path or not self.confirm_replace_draft():
            return
        tiled = messagebox.askyesnocancel("识别方式", "是否分块识别?\n\n密集小字可以选是(最多4次识别请求); 清晰图片选否, 先整图识别.", parent=self)
        if tiled is None:
            return
        snapshot = copy.deepcopy(self.tt)
        signature = service.timetable_signature(self.tt)
        def complete(draft):
            if service.timetable_signature(self.tt) != signature:
                messagebox.showinfo("课表已有变化", "识别期间课表发生变化, 请重新导入以避免覆盖修改.", parent=self)
                return
            self.accept_import(draft.courses, draft.notes)
        self.run_task(lambda: service.import_image(path, snapshot.weeks_total, tiled), complete, "正在识图, 完成后进入校对...")

    def load_demo(self):
        if not self.confirm_replace_draft():
            return
        sample = Path(__file__).resolve().parents[1] / "data" / "示例课表.yaml"
        self.set_timetable(service.load_timetable(sample), ["当前是示例课表预览, 点击保存前不会覆盖原文件."])
        self.review_tab, self.review_week = "周课表", None
        self.go("review")

    def add_course(self, course):
        updated = copy.deepcopy(self.tt)
        updated.courses.append(course)
        self.set_timetable(updated)
        if self.page == "review":
            self.go("review")
        else:
            self._refresh_file_label()

    def show_review(self):
        self.page_title.configure(text="我的课表")
        area = ctk.CTkFrame(self.body, fg_color="transparent")
        area.pack(fill="both", expand=True, padx=28, pady=22)
        area.grid_columnconfigure(0, weight=1)
        area.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(area, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 13))
        for text, command in [("新增课程", lambda: CourseDialog(self, self.add_course)), ("撤销修改", self.undo),
                              ("学期与作息", lambda: SemesterDialog(self, self.tt, self.semester_changed))]:
            Button(toolbar, text=text, width=105, height=33, fg_color="#e5ebf8", text_color=ACCENT, command=command).pack(side="left", padx=(0, 8))
        if self.notice_available:
            Button(toolbar, text="手动调课", width=90, height=33, fg_color="#e5ebf8", text_color=ACCENT, command=self.manual_notice).pack(side="left", padx=(0, 8))
        self.review_tabs = ctk.CTkTabview(
            area, fg_color="white", text_color=INK,
            segmented_button_fg_color=LIGHT, segmented_button_selected_color=LIGHT_ACTIVE,
            segmented_button_selected_hover_color="#bdceff", segmented_button_unselected_color=LIGHT,
            segmented_button_unselected_hover_color=LIGHT_HOVER,
            command=lambda: setattr(self, "review_tab", self.review_tabs.get()),
        )
        self.review_tabs.grid(row=1, column=0, sticky="nsew")
        self.review_tabs.add("周课表")
        self.review_tabs.add("课程列表")
        if self.review_week is None:
            try:
                self.review_week = service.current_week(self.tt)
            except ValueError:
                self.review_week = 1
        self.review_week = max(1, min(self.review_week, self.tt.weeks_total))
        self.calendar_view = WeeklyTimetable(self.review_tabs.tab("周课表"), self.tt, self.review_week,
                                             on_week=lambda week: setattr(self, "review_week", week),
                                             focus_period=self.review_period)
        self.review_period = None
        self.calendar_view.pack(fill="both", expand=True)
        self.review_tabs.set(self.review_tab)
        table_frame = ctk.CTkFrame(self.review_tabs.tab("课程列表"), fg_color="white", corner_radius=14)
        table_frame.pack(fill="both", expand=True)
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(1, weight=1)
        edit_tools = ctk.CTkFrame(table_frame, fg_color="transparent")
        edit_tools.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=7)
        for text, command in [("编辑所选", self.edit_course), ("删除所选", self.delete_courses)]:
            Button(edit_tools, text=text, width=100, fg_color=LIGHT, command=command).pack(side="left", padx=(0, 8))
        label(edit_tools, "双击课程行可编辑基础安排; 单次调整请用调课功能.", 12, MUTED).pack(side="left", padx=7)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Course.Treeview", font=("Microsoft YaHei UI", 12), rowheight=38, background="white", fieldbackground="white", foreground=INK, borderwidth=0)
        style.configure("Course.Treeview.Heading", font=("Microsoft YaHei UI", 12, "bold"), background="#edf1f9", foreground=INK, relief="flat")
        style.map("Course.Treeview", background=[("selected", "#dce5ff")], foreground=[("selected", "#243d88")])
        columns = ("name", "day", "periods", "weeks", "room", "changes")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", style="Course.Treeview", selectmode="extended")
        for key, title, width in zip(columns, ["课程名称", "星期", "节次", "周次", "地点", "调整"], [180, 65, 65, 165, 175, 100]):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=55, anchor="w")
        self.tree.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 0))
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=12, padx=(0, 8))
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        horizontal.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        for index, course in sorted(enumerate(self.tt.courses), key=lambda pair: (pair[1].day, pair[1].start, pair[1].name)):
            annotations = f"停 {len(course.skip)} / 调 {len(course.changes)}" if course.skip or course.changes else ""
            self.tree.insert("", "end", iid=str(index), values=(course.name, course.day_name, f"{course.start}-{course.end}", course.weeks, course.room, annotations))
        self.tree.bind("<Double-1>", lambda event: self.edit_course())
        review = service.review_timetable(self.tt)
        header = f"时间冲突 {len(review.conflicts)}  /  待完善 {len(review.issues)}  /  调整记录 {len(review.changes)}"
        summary = ctk.CTkFrame(area, fg_color="transparent")
        summary.grid(row=2, column=0, sticky="ew", pady=(9, 3))
        label(summary, header, 13, "#a45f29" if review.problem_count else "#18835b").pack(side="left")
        details = self.notes + self.tt.warnings + review.conflicts + review.issues + review.changes
        notices = service.holiday_notices(self.tt)
        details.extend(notices.warnings)
        details.extend(notices.lines())
        box = ctk.CTkTextbox(area, height=128, fg_color="white", font=("Microsoft YaHei UI", 12))
        box.grid(row=3, column=0, sticky="ew")
        box.insert("1.0", "\n".join(details) if details else "未发现明显问题. 双击课程行可编辑; 日历与周视图会应用停课和调课.")
        box.configure(state="disabled")
        def toggle_details():
            self.review_details_open = not self.review_details_open
            if self.review_details_open:
                box.grid()
            else:
                box.grid_remove()
            toggle.configure(text="收起校对详情" if self.review_details_open else "展开校对详情")
        toggle = Button(summary, text="收起校对详情" if self.review_details_open else "展开校对详情",
                        width=120, height=28, fg_color=LIGHT, command=toggle_details)
        toggle.pack(side="right")
        if not self.review_details_open:
            box.grid_remove()

    def show_course_list(self):
        self.review_tab = "课程列表"
        self.go("review")

    def edit_course(self):
        if not getattr(self, "tree", None) or not self.tree.winfo_exists():
            return
        selected = self.tree.selection()
        if len(selected) != 1:
            messagebox.showinfo("请选择课程", "请先选择一门课程再编辑.", parent=self)
            return
        index = int(selected[0])
        signature = service.timetable_signature(self.tt)
        def accept(course):
            if service.timetable_signature(self.tt) != signature:
                raise ValueError("编辑期间课表已变化, 请关闭后重新选择课程.")
            updated = copy.deepcopy(self.tt)
            updated.courses[index] = course
            self.set_timetable(updated)
            self.go("review")
        CourseDialog(self, accept, self.tt.courses[index])

    def delete_courses(self):
        selected = self.tree.selection()
        if not selected:
            return
        if messagebox.askyesno("删除所选课程", f"删除 {len(selected)} 条课程? 保存前可撤销.", parent=self):
            updated = copy.deepcopy(self.tt)
            for index in sorted((int(i) for i in selected), reverse=True):
                del updated.courses[index]
            self.set_timetable(updated)
            self.go("review")

    def semester_changed(self, timetable):
        self.set_timetable(timetable)
        self.go(self.page)

    def save(self, as_new=False):
        path = self.source
        if as_new:
            selected = filedialog.asksaveasfilename(parent=self, title="另存课表文件", defaultextension=".yaml", initialfile=path.name, filetypes=[("课表源文件", "*.yaml")])
            if not selected:
                return False
            path = Path(selected)
        try:
            expected = self.saved_signature if path == self.source else None
            service.save_timetable(self.tt, path, expected_signature=expected)
            self.source = path
            self.saved_signature = service.file_signature(path)
            self.dirty = False
            service.remember_current_source(path)
            self._refresh_file_label()
            self.status.configure(text="当前课表已保存, 可以直接在应用内查看和继续修改.")
            return True
        except (OSError, ValueError) as exc:
            messagebox.showerror("保存未完成", str(exc), parent=self)
            return False

    def open_source(self):
        if self.dirty:
            answer = messagebox.askyesnocancel("打开前保存", "是否先保存当前修改? 选择否将放弃当前预览.", parent=self)
            if answer is None or (answer and not self.save()):
                return
        path = filedialog.askopenfilename(parent=self, title="打开课表", filetypes=[("课表源文件", "*.yaml *.yml")])
        if path:
            try:
                self.tt = service.load_timetable(path)
                self.source = Path(path)
                self.saved_signature = service.file_signature(path)
                self.dirty, self.notes, self.undo_stack = False, [], []
                self.review_tab, self.review_week = "周课表", None
                service.remember_current_source(self.source)
                self.go("review")
            except (ValueError, OSError) as exc:
                messagebox.showerror("打开未完成", str(exc), parent=self)

    def open_notice(self):
        if not self.tt.courses:
            messagebox.showinfo("先导入课表", "请先导入或录入课表, 再使用通知调课.", parent=self)
            return
        if self.ensure_ai():
            from .notice_dialog import NoticeDialog
            NoticeDialog(self)

    def manual_notice(self):
        from .notice_dialog import NoticeDialog
        if self.tt.courses:
            NoticeDialog(self, use_ai=False)

    def persist_adjustment(self, preview):
        result = service.apply_notification(self.tt, preview)
        path = self.source
        service.save_timetable(result, path, expected_signature=self.saved_signature)
        self.set_timetable(result, [f"{old} -> {new}" for old, new in preview.rows])
        self.source = path
        self.saved_signature = service.file_signature(path)
        self.dirty = False
        service.remember_current_source(path)
        self.review_week = preview.focus_week or self.review_week
        self.review_period = preview.focus_period
        self.review_tab = "周课表"
        self._refresh_file_label()
        self.status.configure(text="当前课表已修改并保存, 周课表已显示调整后的安排.")
        return True

    def show_export(self):
        self.page_title.configure(text="生成你每天会看到的课表")
        outer = ctk.CTkFrame(self.body, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=26, pady=22)
        outer.grid_columnconfigure(1, weight=1)
        outer.grid_rowconfigure(0, weight=1)
        controls = ctk.CTkScrollableFrame(outer, width=270, fg_color="white", corner_radius=14)
        controls.grid(row=0, column=0, sticky="ns", padx=(0, 18))
        label(controls, "输出设置", 19).pack(anchor="w", padx=15, pady=(16, 13))
        self.export_fields = {}
        values = [
            ("week", "视图", ["学期总览"] + [f"第 {w} 周" for w in range(1, self.tt.weeks_total + 1)]),
            ("background", "背景", ["黄昏晚霞", "深夜星河", "海盐渐变", "暮紫渐变"]),
            ("theme", "主题", ["经典深色", "清爽浅色", "打印白底"]),
            ("which", "壁纸尺寸", ["电脑和手机", "仅电脑", "仅手机"]),
        ]
        for key, title, options in values:
            label(controls, title, 12, MUTED).pack(anchor="w", padx=15, pady=(9, 4))
            menu = OptionMenu(controls, values=options, width=235, fg_color="#edf1fa", text_color=INK)
            menu.pack(fill="x", padx=15)
            self.export_fields[key] = menu
        self.custom_bg = None
        self.bg_label = label(controls, "未选择自定义背景", 11, MUTED, wraplength=235)
        self.bg_label.pack(anchor="w", padx=15, pady=(14, 5))
        Button(controls, text="选择 / 清除自定义图片", fg_color="#edf1fa", text_color=ACCENT, command=self.choose_background).pack(fill="x", padx=15)
        self.alpha = tk.DoubleVar(value=190)
        self.blur = tk.DoubleVar(value=6)
        self.brightness = tk.DoubleVar(value=.62)
        self.top_safe = tk.DoubleVar(value=0)
        self.bottom_safe = tk.DoubleVar(value=0)
        for title, variable, lower, upper in [("课块不透明度", self.alpha, 60, 255), ("背景模糊", self.blur, 0, 20),
                                              ("背景亮度", self.brightness, .25, 1), ("顶部安全边距", self.top_safe, 0, .25),
                                              ("底部安全边距", self.bottom_safe, 0, .2)]:
            label(controls, title, 12, MUTED).pack(anchor="w", padx=15, pady=(13, 4))
            ctk.CTkSlider(controls, from_=lower, to=upper, variable=variable).pack(fill="x", padx=15)
        self.set_wallpaper = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(controls, text="导出后设为电脑壁纸", variable=self.set_wallpaper, font=("Microsoft YaHei UI", 12)).pack(anchor="w", padx=15, pady=18)
        preview = ctk.CTkFrame(outer, fg_color="white", corner_radius=14)
        preview.grid(row=0, column=1, sticky="nsew")
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_rowconfigure(1, weight=1)
        label(preview, "壁纸预览", 18).grid(row=0, column=0, sticky="w", padx=20, pady=18)
        self.preview_label = label(preview, "点击下方更新预览\n预览和导出均使用当前已校对的课表", 15, MUTED)
        self.preview_label.grid(row=1, column=0, sticky="nsew", padx=15)
        actions = ctk.CTkFrame(preview, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=18, pady=18)
        for text, command in [("更新预览", self.update_preview), ("导出壁纸", self.export_wallpapers), ("导出日历", self.export_calendar)]:
            Button(actions, text=text, width=105, height=35, fg_color=ACCENT if text == "导出壁纸" else "#edf1fa", text_color="white" if text == "导出壁纸" else ACCENT, command=command).pack(side="left", padx=(0, 8))
        if self.poster_available:
            extra = ctk.CTkFrame(preview, fg_color="transparent")
            extra.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
            for text, command in [("A4 挂图", self.export_poster), ("分享卡", self.export_share)]:
                Button(extra, text=text, width=105, height=32, fg_color="#edf1fa", text_color=ACCENT, command=command).pack(side="left", padx=(0, 8))

    def export_options(self):
        week_text = self.export_fields["week"].get()
        return {
            "week": None if week_text == "学期总览" else int(week_text.split()[1]),
            "background": {"黄昏晚霞": "dusk", "深夜星河": "night", "海盐渐变": "sea", "暮紫渐变": "purple"}[self.export_fields["background"].get()],
            "theme": {"经典深色": "dark", "清爽浅色": "light", "打印白底": "paper"}[self.export_fields["theme"].get()],
            "bg_image": self.custom_bg, "block_alpha": int(self.alpha.get()), "blur": self.blur.get(),
            "text_mode": "auto",
            "brightness": self.brightness.get(), "top_safe": self.top_safe.get(), "bottom_safe": self.bottom_safe.get(),
        }

    def choose_background(self):
        if self.custom_bg and messagebox.askyesno("自定义背景", "清除当前自定义图片并使用内置背景吗?", parent=self):
            self.custom_bg = None
        else:
            path = filedialog.askopenfilename(parent=self, title="选择背景图片", filetypes=[("图片", "*.png *.jpg *.jpeg *.webp *.bmp")])
            if path:
                self.custom_bg = path
        self.bg_label.configure(text=Path(self.custom_bg).name if self.custom_bg else "未选择自定义背景")

    def update_preview(self):
        options = self.export_options()
        snapshot = copy.deepcopy(self.tt)
        options["size"] = (1280, 800)
        def complete(image):
            if self.page != "export":
                return
            width = max(480, self.preview_label.winfo_width() - 10)
            height = max(280, self.preview_label.winfo_height() - 10)
            image.thumbnail((width, height), Image.Resampling.LANCZOS)
            self._preview_image = ctk.CTkImage(image, size=image.size)
            self.preview_label.configure(text="", image=self._preview_image)
        self.run_task(lambda: service.preview_wallpaper(snapshot, **options), complete, "正在生成预览...")

    def export_wallpapers(self):
        folder = filedialog.askdirectory(parent=self, title="选择壁纸输出目录")
        if not folder:
            return
        options = self.export_options()
        which = {"电脑和手机": "both", "仅电脑": "desktop", "仅手机": "phone"}[self.export_fields["which"].get()]
        snapshot, set_desktop = copy.deepcopy(self.tt), self.set_wallpaper.get()
        def complete(results):
            try:
                if set_desktop:
                    desktop = next((path for path, size in results if "电脑" in path.name), None)
                    if desktop is None:
                        raise ValueError("本次仅导出了手机壁纸, 请改选电脑尺寸后再设为桌面.")
                    service.set_desktop_wallpaper(desktop)
                messagebox.showinfo("壁纸已导出", "\n".join(str(path) for path, size in results), parent=self)
            except (ValueError, OSError) as exc:
                messagebox.showerror("设置壁纸未完成", str(exc), parent=self)
        self.run_task(lambda: service.render_wallpapers(snapshot, folder, which=which, **options), complete, "正在导出壁纸...")

    def export_calendar(self):
        path = filedialog.asksaveasfilename(parent=self, title="导出日历", initialfile="课表.ics", defaultextension=".ics", filetypes=[("日历文件", "*.ics")])
        if not path:
            return
        try:
            result = service.export_calendar(self.tt, path)
            messagebox.showinfo("日历已导出", f"已导出 {result.name}. 可导入手机或电脑日历, 默认课前15分钟提醒.", parent=self)
        except (ValueError, OSError) as exc:
            messagebox.showerror("请先完善课表", str(exc), parent=self)

    def export_poster(self):
        path = filedialog.asksaveasfilename(parent=self, title="导出 A4 挂图", initialfile="课表挂图.pdf", defaultextension=".pdf", filetypes=[("A4 PDF", "*.pdf"), ("300dpi PNG", "*.png")])
        if path:
            snapshot, week = copy.deepcopy(self.tt), self.export_options()["week"]
            self.run_task(lambda: service.export_poster(snapshot, path, week), lambda result: messagebox.showinfo("挂图已导出", str(result), parent=self), "正在生成 A4 挂图...")

    def export_share(self):
        path = filedialog.asksaveasfilename(parent=self, title="导出分享卡", initialfile="课表分享卡.png", defaultextension=".png", filetypes=[("PNG 图片", "*.png")])
        if path:
            snapshot, week = copy.deepcopy(self.tt), self.export_options()["week"]
            self.run_task(lambda: service.export_share_card(snapshot, path, week), lambda result: messagebox.showinfo("分享卡已导出", str(result), parent=self), "正在生成分享卡...")

    def run_task(self, function, complete, status="正在处理...", failure=None):
        if self._busy:
            messagebox.showinfo("请稍候", "上一个任务还在处理中, 请完成后再继续.", parent=self)
            return False
        self._busy = True
        self.status.configure(text=status)
        self.progress.start()
        def execute():
            try:
                value = function()
                self._results.put((True, value, complete, failure))
            except Exception as exc:
                self._results.put((False, exc, complete, failure))
        threading.Thread(target=execute, daemon=True).start()
        return True

    def _poll(self):
        if self._closing:
            return
        try:
            ok, value, complete, failure = self._results.get_nowait()
            self._busy = False
            self.progress.stop()
            self.progress.set(0)
            self.status.configure(text="已完成, 请核对结果." if ok else "操作未完成, 原课表保持原样.")
            if ok:
                complete(value)
            elif failure:
                failure(value)
            else:
                messagebox.showerror("操作未完成", str(value), parent=self)
        except queue.Empty:
            pass
        except Exception as exc:
            messagebox.showerror("结果未能显示", str(exc), parent=self)
        self.after(80, self._poll)

    def close_app(self):
        if self._busy and not messagebox.askyesno("任务仍在处理", "仍有任务在处理, 确定关闭窗口吗? 未确认的结果不会保存.", parent=self):
            return
        if self.dirty:
            answer = messagebox.askyesnocancel("保存修改", "是否保存当前课表修改后再关闭?", parent=self)
            if answer is None or (answer and not self.save()):
                return
        self._closing = True
        self.destroy()
