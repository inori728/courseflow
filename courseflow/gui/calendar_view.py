"""Live weekly timetable, using resolved occurrences rather than exported images."""
from __future__ import annotations

import hashlib
import tkinter as tk
from tkinter import font as tkfont, messagebox, ttk

import customtkinter as ctk

from .. import service
from ..model import DAYS
from .dialogs import label
from .styles import INK, LIGHT, MUTED, Button, OptionMenu

COLORS = ["#dce5ff", "#d7f1e6", "#ffe5d5", "#e9ddf8", "#d8eef3", "#f8dfe7"]


class WeeklyTimetable(ctk.CTkFrame):
    def __init__(self, master, timetable, week=1, on_week=None, focus_period=None):
        super().__init__(master, fg_color="white", corner_radius=0)
        self.timetable = timetable
        self.week = max(1, min(week, timetable.weeks_total))
        self.on_week = on_week
        self._draw_job = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 7))
        self.previous = Button(controls, text="上一周", width=70, fg_color=LIGHT, command=lambda: self.set_week(self.week - 1))
        self.previous.pack(side="left", padx=(0, 7))
        self.week_options = [f"第 {number} 周" for number in range(1, timetable.weeks_total + 1)]
        self.menu = OptionMenu(controls, values=self.week_options, width=110,
                               command=lambda value: self.set_week(self.week_options.index(value) + 1))
        self.menu.pack(side="left", padx=(0, 7))
        self.next = Button(controls, text="下一周", width=70, fg_color=LIGHT, command=lambda: self.set_week(self.week + 1))
        self.next.pack(side="left", padx=(0, 7))
        Button(controls, text="回到本周", width=95, fg_color=LIGHT, command=self.this_week).pack(side="left", padx=(0, 12))
        self.summary = label(controls, "", 13, MUTED)
        self.summary.pack(side="left")
        self.header = tk.Canvas(self, height=self.s(49), background="white", highlightthickness=0)
        self.header.grid(row=1, column=0, sticky="ew")
        self.canvas = tk.Canvas(self, background="white", highlightthickness=0, yscrollincrement=self.s(27))
        self.canvas.grid(row=2, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        scroll.grid(row=2, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.bind("<Configure>", lambda event: self._schedule_draw())
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda event: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda event: self.canvas.yview_scroll(1, "units"))
        self.hint = label(self, "", 12, MUTED, wraplength=850, justify="left", anchor="w")
        self.hint.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
        self.set_week(self.week, focus_period=focus_period)

    def s(self, value):
        return round(self._apply_widget_scaling(value))

    def _wheel(self, event):
        delta = round(event.delta / 120) or (1 if event.delta > 0 else -1)
        self.canvas.yview_scroll(-delta, "units")
        return "break"

    def this_week(self):
        try:
            week = service.current_week(self.timetable)
        except ValueError:
            week = 1
        self.set_week(max(1, min(week, self.timetable.weeks_total)))

    def set_week(self, week, focus_period=None):
        if not 1 <= week <= self.timetable.weeks_total:
            return
        self.week = week
        self._pending_focus = focus_period
        self.data = service.week_calendar_data(self.timetable, week)
        self.menu.set(self.week_options[week - 1])
        self.previous.configure(state="disabled" if week == 1 else "normal")
        self.next.configure(state="disabled" if week == self.timetable.weeks_total else "normal")
        self.summary.configure(text=f"{len(self.data['courses'])} 次已确认课程")
        hints = [self.data["date_note"]] if self.data["date_note"] else []
        if self.data["unknown"]:
            hints.append("周次待确认, 未计入此周: " + ", ".join(self.data["unknown"]))
        hints.append("点击课块查看详情; 停课和调课已按本周实际安排显示.")
        self.hint.configure(text="\n".join(hints))
        self.canvas.yview_moveto(0)
        if self.on_week:
            self.on_week(week)
        self._schedule_draw()

    def _schedule_draw(self):
        if self._draw_job is None:
            self._draw_job = self.after_idle(self._draw_calendar)

    def _wrapped(self, text, font, width, limit):
        lines, line = [], ""
        for char in str(text):
            if line and font.measure(line + char) > width:
                lines.append(line)
                line = ""
                if len(lines) == limit:
                    while lines[-1] and font.measure(lines[-1] + "...") > width:
                        lines[-1] = lines[-1][:-1]
                    lines[-1] += "..."
                    return "\n".join(lines)
            line += char
        if line:
            lines.append(line)
        return "\n".join(lines)

    def _draw_calendar(self):
        self._draw_job = None
        if not self.winfo_exists():
            return
        self.canvas.delete("all")
        self.header.delete("all")
        self.header.configure(height=self.s(49))
        width = max(self.s(700), self.canvas.winfo_width())
        gutter, row_height = self.s(52), self.s(54)
        column = (width - gutter) / 7
        height = row_height * 12
        self.canvas.configure(scrollregion=(0, 0, width, height))
        self.title_font = tkfont.Font(font=self._apply_font_scaling(("Microsoft YaHei UI", 13, "bold")))
        self.small_font = tkfont.Font(font=self._apply_font_scaling(("Microsoft YaHei UI", 12)))
        self.clock_font = tkfont.Font(font=self._apply_font_scaling(("Microsoft YaHei UI", 10)))
        self.header.create_text(gutter / 2, self.s(24), text="节次", font=self.small_font, fill=MUTED)
        for day, name in enumerate(DAYS):
            center = gutter + (day + .5) * column
            self.header.create_text(center, self.s(16), text=name, font=self.title_font, fill=INK)
            if self.data["dates"]:
                self.header.create_text(center, self.s(37), text=self.data["dates"][day].strftime("%m-%d"), font=self.clock_font, fill=MUTED)
        for row in range(12):
            top = row * row_height
            self.canvas.create_rectangle(0, top, width, top + row_height, fill="#f8faff" if row % 2 == 0 else "white", outline="#e4e9f2")
            self.canvas.create_text(gutter / 2, top + self.s(19), text=str(row + 1), font=self.small_font, fill=INK)
            if row + 1 in self.timetable.period_times:
                clock = self.timetable.period_times[row + 1][0].strftime("%H:%M")
                self.canvas.create_text(gutter / 2, top + self.s(38), text=clock, font=self.clock_font, fill=MUTED)
        for day in range(8):
            x = gutter + day * column
            self.canvas.create_line(x, 0, x, height, fill="#e4e9f2")
        self.visible_courses = list(self.data["courses"])
        for day in range(7):
            entries = sorted([item for item in self.visible_courses if item.day == day], key=lambda item: (item.start, item.end, item.name))
            clusters, cluster, last = [], [], 0
            for entry in entries:
                if cluster and entry.start > last:
                    clusters.append(cluster)
                    cluster = []
                cluster.append(entry)
                last = max(item.end for item in cluster)
            if cluster:
                clusters.append(cluster)
            for cluster in clusters:
                lanes, placed = [], []
                for entry in cluster:
                    lane = next((index for index, end in enumerate(lanes) if end < entry.start), len(lanes))
                    if lane == len(lanes):
                        lanes.append(entry.end)
                    else:
                        lanes[lane] = entry.end
                    placed.append((entry, lane))
                for entry, lane in placed:
                    left = gutter + day * column + lane * column / len(lanes) + self.s(3)
                    right = gutter + day * column + (lane + 1) * column / len(lanes) - self.s(3)
                    top, bottom = (entry.start - 1) * row_height + self.s(3), entry.end * row_height - self.s(3)
                    color = COLORS[hashlib.sha1(entry.name.encode("utf-8")).digest()[0] % len(COLORS)]
                    tag = f"course-{day}-{len(self.canvas.find_withtag('course'))}"
                    self.canvas.create_rectangle(left, top, right, bottom, fill=color, outline=color, tags=(tag, "course"))
                    text_width = max(self.s(10), right - left - self.s(12))
                    name = self._wrapped(entry.name, self.title_font, text_width, 2)
                    self.canvas.create_text(left + self.s(6), top + self.s(5), text=name, anchor="nw", font=self.title_font, fill=INK, tags=tag)
                    room_y = top + self.s(7) + len(name.splitlines()) * self.title_font.metrics("linespace")
                    if room_y + self.small_font.metrics("linespace") < bottom:
                        room = self._wrapped(entry.room or "地点未填写", self.small_font, text_width, 1)
                        self.canvas.create_text(left + self.s(6), room_y, text=room, anchor="nw", font=self.small_font, fill="#425372", tags=tag)
                    self.canvas.tag_bind(tag, "<Button-1>", lambda event, item=entry: self._details(item))
        if self._pending_focus is not None:
            self.canvas.yview_moveto(max(0, self._pending_focus - 2) / 12)
            self._pending_focus = None

    def _details(self, entry):
        text = f"第 {entry.week} 周 {DAYS[entry.day]} {entry.start}-{entry.end} 节\n地点: {entry.room or '未填写'}"
        if entry.source_week != entry.week:
            text += f"\n由第 {entry.source_week} 周调整到本周."
        messagebox.showinfo(entry.name, text, parent=self.winfo_toplevel())

    def destroy(self):
        if self._draw_job is not None:
            self.after_cancel(self._draw_job)
            self._draw_job = None
        super().destroy()
