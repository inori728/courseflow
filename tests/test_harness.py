import base64
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops, ImageStat

from courseflow import service
from courseflow.backgrounds import BACKGROUNDS, make_background
from courseflow.harness import Harness, SettingsRequired
from courseflow.model import Course, Timetable
from courseflow.semester import SCHOOL_CLOCKS
from courseflow.settings import AIConfig
from courseflow.source import save_source


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.source = self.home / "课表.yaml"
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"COURSEFLOW_HOME": str(self.home), "COURSEFLOW_SOURCE": str(self.source)}).start()
        self.harness = Harness()
        self.tt = service.configure_semester(
            Timetable(courses=[
                Course("体育", 1, 3, 4, "操场", "1-16周"),
                Course("体育", 3, 3, 4, "操场", "1-16周"),
                Course("数学", 4, 3, 4, "A302", "7周"),
            ]),
            "示例", date(2026, 9, 7), 16, SCHOOL_CLOCKS,
        )
        save_source(self.tt, self.source)

    def invoke(self, action, **payload):
        return self.harness.run(action, payload)

    def preview_move(self, week):
        prepared = self.invoke("request", text=f"把第{week}周周二的体育课调到周五第4大节")
        return self.invoke("preview", token=prepared["token"])["confirmation"]

    def test_duplicate_matches_require_selection_and_save_once(self):
        original = self.source.read_bytes()
        prepared = self.invoke("request", text="把第7周的体育课调到周五第4大节\uff0c地点不变")
        proposed = self.invoke("preview", token=prepared["token"])
        self.assertEqual(len(proposed["candidates"]), 2)
        self.assertNotIn("confirmation", proposed)
        self.assertEqual(self.source.read_bytes(), original)
        selected = self.invoke("preview", token=prepared["token"], selected=[proposed["candidates"][0]["id"]])
        self.assertIn("16:00-17:40", selected["rows"][0]["after"])
        result = self.invoke("commit", token=selected["confirmation"])
        self.assertEqual(result, self.invoke("commit", token=selected["confirmation"]))
        self.assertTrue(result["updated"])
        self.assertEqual(self.source.with_suffix(".yaml.bak").read_bytes(), original)
        week = service.week_calendar_data(service.load_timetable(self.source), 7)
        self.assertEqual([(occ.day, occ.start) for occ in week["courses"] if occ.name == "体育"], [(4, 7), (3, 3)])

    def test_conflict_and_concurrent_edits_are_rejected(self):
        conflict = self.invoke("request", text="把第7周周二的体育课调到周五第2大节")
        result = self.invoke("preview", token=conflict["token"])
        self.assertTrue(result["conflicts"])
        self.assertNotIn("confirmation", result)
        okay = self.invoke("request", text="把第7周周二的体育课调到周五第4大节")
        result = self.invoke("preview", token=okay["token"])
        self.tt.term = "在桌面端编辑"
        save_source(self.tt, self.source)
        with self.assertRaisesRegex(ValueError, "在预览后已更新"):
            self.invoke("commit", token=result["confirmation"])
        self.assertEqual(service.load_timetable(self.source).term, self.tt.term)

    def test_undo_removes_only_latest_save_and_survives_export_and_restart(self):
        self.invoke("commit", token=self.preview_move(7))
        first_change = self.source.read_bytes()
        first_undo = self.invoke("status", full=True)["undo"]
        second_commit = self.preview_move(8)
        self.invoke("commit", token=second_commit)
        second_change = self.source.read_bytes()
        self.assertNotEqual(first_change, second_change)
        with self.assertRaisesRegex(ValueError, "无法撤销"):
            self.invoke("undo", token=first_undo["token"])

        export = self.invoke("request", mode="export", formats=["yaml"])
        preview = self.invoke("preview", token=export["token"])
        self.invoke("commit", token=preview["confirmation"])
        reopened = Harness()
        undo = reopened.run("status", {"full": True})["undo"]
        self.assertEqual(undo["label"], "调课")
        self.assertTrue(reopened.run("undo", {"token": undo["token"]})["updated"])
        self.assertEqual(self.source.read_bytes(), first_change)
        self.assertEqual(self.source.with_suffix(".yaml.bak").read_bytes(), second_change)
        self.assertIsNone(self.invoke("status", full=True)["undo"])
        with self.assertRaisesRegex(ValueError, "无法撤销"):
            reopened.run("undo", {"token": undo["token"]})
        self.invoke("commit", token=second_commit)
        self.assertEqual(self.source.read_bytes(), first_change)

    def test_undo_does_not_overwrite_a_desktop_save(self):
        self.invoke("commit", token=self.preview_move(7))
        undo = self.invoke("status", full=True)["undo"]
        desktop = service.load_timetable(self.source)
        desktop.term = "桌面端另一次保存"
        service.save_timetable(desktop, self.source)
        changed_elsewhere = self.source.read_bytes()
        self.assertIsNone(self.invoke("status", full=True)["undo"])
        with self.assertRaisesRegex(ValueError, "无法撤销"):
            self.invoke("undo", token=undo["token"])
        self.assertEqual(self.source.read_bytes(), changed_elsewhere)

    def test_failed_replacement_keeps_the_last_successful_undo(self):
        original = self.source.read_bytes()
        self.invoke("commit", token=self.preview_move(7))
        undo = self.invoke("status", full=True)["undo"]
        first_change = self.source.read_bytes()
        second_commit = self.preview_move(8)

        write_bytes = service.atomic_bytes

        def deny_timetable_replacement(path, contents):
            if path == self.source:
                raise OSError("timetable temporarily locked")
            write_bytes(path, contents)

        with patch("courseflow.service.atomic_bytes", side_effect=deny_timetable_replacement):
            with self.assertRaisesRegex(OSError, "temporarily locked"):
                self.invoke("commit", token=second_commit)
        self.assertEqual(self.source.read_bytes(), first_change)
        self.assertEqual(self.invoke("status", full=True)["undo"], undo)
        self.invoke("undo", token=undo["token"])
        self.assertEqual(self.source.read_bytes(), original)
        self.assertIsNone(self.invoke("status", full=True)["undo"])

    def test_attached_table_exports_without_replacing_active_timetable(self):
        original = self.source.read_bytes()
        incoming = service.configure_semester(
            Timetable(courses=[Course("体育", 1, 3, 4, "操场", "7周")]),
            "上传课表", date(2026, 9, 7), 16, SCHOOL_CLOCKS,
        )
        attach_path = self.home / "附件.yaml"
        save_source(incoming, attach_path)
        attachment = {"name": attach_path.name, "base64": base64.b64encode(attach_path.read_bytes()).decode("ascii")}
        prepared = self.invoke("request", files=[attachment], text="把第7周周二的体育课调到周五第4大节\uff0c再生成深色手机壁纸\uff0c导出课表和日历")
        preview = self.invoke("preview", token=prepared["token"])
        result = self.invoke("commit", token=preview["confirmation"])
        self.assertFalse(result["updated"])
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(len(result["files"]), 3)
        paths = [self.harness.exports / item["id"] for item in result["files"]]
        self.assertTrue(all(path.is_file() for path in paths))
        calendar = next(path for path in paths if path.suffix == ".ics")
        self.assertIn("DTSTART:20261023T080000Z", calendar.read_text(encoding="utf-8"))

    def test_group_event_uses_selected_time_and_reappears_as_busy(self):
        member = service.make_busy_card(self.tt, "同学", weeks=[7])
        prepared = self.invoke("request", text="查第7周共同空闲\uff0c加入我的课表", shortcodes=[member.encode()])
        searched = self.invoke("group_search", token=prepared["token"], week=7,
                               minimum=2, members=[{"name": "同学"}], include_self=True)
        self.assertEqual(searched["clocks"]["12"], "21:55-22:40")
        saved = self.invoke("activity", token=searched["token"], day=4, start=7, end=8,
                            title="小组汇报", room="B206", export_ics=True)
        timetable = service.load_timetable(self.source)
        event = next(course for course in timetable.courses if course.kind == "activity")
        self.assertEqual((event.name, event.start, event.end), ("小组汇报", 7, 8))
        calendar = (self.harness.exports / saved["files"][0]["id"]).read_text(encoding="utf-8")
        self.assertIn("LOCATION:B206", calendar)
        found = self.invoke("group_refresh", token=searched["token"])
        self.assertEqual(found["counts"][4 * 12 + 6:4 * 12 + 8], [1, 1])
        with self.assertRaisesRegex(ValueError, "在预览后已更新"):
            self.invoke("activity", token=searched["token"], day=4, start=7, end=8, title="重复提交")
        grid = self.invoke("point_grid", token=found["token"])
        self.assertTrue((self.harness.exports / grid["files"][0]["id"]).is_file())
        undo = self.invoke("status", full=True)["undo"]
        self.assertEqual(undo["label"], "添加组队活动")
        self.invoke("undo", token=undo["token"])
        restored = self.invoke("group_refresh", token=searched["token"])
        self.assertEqual(restored["counts"][4 * 12 + 6:4 * 12 + 8], [0, 0])

    def test_single_week_busy_card_defaults_to_its_coverage(self):
        card = service.make_busy_card(self.tt, "虚构组员", weeks=[12])
        with patch("courseflow.harness_commands.local_today", return_value=date(2026, 12, 2)):
            for text, expected in (("", 12), ("查第13周", 13), ("查本周", 13), ("查下周", 14)):
                with self.subTest(text=text):
                    prepared = self.invoke("request", mode="group", text=text, shortcodes=[card.encode()])
                    self.assertEqual(prepared["week"], expected)

    def test_next_searches_files_and_shortcodes_together_in_addition_order(self):
        first = service.make_busy_card(replace(self.tt, courses=[]), "成员一", weeks=[7])
        later_anchor = self.tt.semester_start + timedelta(weeks=1)
        second = service.make_busy_card(replace(self.tt, courses=[], semester_start=later_anchor), "成员二", weeks=[6])
        third = service.make_busy_card(replace(self.tt, courses=[]), "成员三", weeks=[7])
        first.busy[7].add(0)
        second.busy[6].add(2)
        third.busy[7].add(4)
        files = [{"name": "成员忙闲卡.busycard", "base64": base64.b64encode(card.encode().encode()).decode()}
                 for card in (first, third)]
        queued = {"mode": "group", "search_now": True, "files": files, "shortcodes": [second.encode()],
                  "member_order": ["file", "code", "file"]}
        group = self.invoke("request", **queued)
        self.assertEqual((group["type"], group["week"]), ("group_result", 7))
        self.assertEqual(group["names"], ["成员一", "成员二", "成员三"])
        self.assertEqual(group["counts"][:6], [1, 0, 1, 0, 1, 0])

        review = self.invoke("request", **queued, text="查第8周共同空闲")
        self.assertEqual(review["type"], "group_prepare")
        self.assertEqual([member["name"] for member in review["members"]], group["names"])
        self.assertIn("没有提供第 8 周", review["warning"])
        self.assertEqual(self.invoke("group_search", token=review["token"], week=7,
                                     members=[{"name": name} for name in group["names"]])["counts"], group["counts"])

    def test_direct_schedule_selection_reuses_pair_and_continues_after_clock_review(self):
        self.source.unlink()
        preset_card = service.make_busy_card(replace(self.tt, courses=[], period_times={}), "虚构组员", weeks=[7])
        group = self.invoke("request", mode="group", shortcodes=[preset_card.encode()], search_now=True)
        schedule = self.invoke("request", group_token=group["token"], text="选空档 周三第7小节 优先连堂 并打开日程")
        self.assertEqual(schedule["type"], "schedule")
        self.assertEqual((schedule["draft"]["start"], schedule["draft"]["end"]), ("16:00", "17:40"))
        self.assertTrue(schedule["activity_token"])
        self.assertFalse(self.source.exists())

        card = replace(preset_card, period_times={1: (time(8, 10), time(8, 50))})
        group = self.invoke("request", mode="group", shortcodes=[card.encode()], search_now=True)
        clock_review = self.invoke("activity_preview", group_token=group["token"], day=2, start=1, end=2,
                                   open_schedule=True)
        self.assertTrue(clock_review["open_schedule"])
        self.assertTrue(clock_review["needs_clocks"])
        schedule = self.invoke("activity_clocks", slot=clock_review["token"], clocks={"2": "08:55-09:35"})
        self.assertEqual(schedule["type"], "schedule")
        self.assertEqual((schedule["draft"]["start"], schedule["draft"]["end"]), ("08:10", "09:35"))
        self.assertEqual(schedule["group"]["names"], [card.name])

    def test_group_reports_semester_length_and_can_retry_same_query_after_correction(self):
        card = service.make_busy_card(replace(self.tt, courses=[]), "虚构组员", weeks=[12])
        card.busy[12].add(12)
        self.tt.courses.append(Course("虚构跨周课程", 0, 5, 6, "示例教室", "4-19周"))
        save_source(self.tt, self.source)
        prepared = self.invoke("request", mode="group", text="查第12周", shortcodes=[card.encode()], include_self=True)
        context = {"group_prepare": prepared["token"]}
        with self.assertRaisesRegex(ValueError, "学期总周数为 16 周.*第 19 周"):
            self.invoke("request", text="确认组队", workbench=context)
        save_source(replace(self.tt, weeks_total=19), self.source)
        group = self.invoke("request", text="确认组队", workbench=context)
        self.assertEqual(group["week"], 12)
        self.assertEqual(group["counts"][4:6], [1, 1])
        self.assertEqual(group["counts"][12], 1)
        with self.assertRaisesRegex(ValueError, r"没有提供第 13 周.*2026-11-30"):
            self.invoke("request", text="确认组队 第13周", workbench=context)

    def test_clockless_busy_card_uses_compatible_personal_clocks_by_default(self):
        self.tt.period_times[7] = (time(16, 5), time(16, 50))
        save_source(self.tt, self.source)
        original = self.source.read_bytes()
        member = service.make_busy_card(replace(self.tt, period_times={}), "虚构组员", weeks=[7])
        prepared = self.invoke("request", text=f"查第7周共同空闲 {member.encode()}")
        group = self.invoke("group_search", token=prepared["token"], week=7, members=[{"name": member.name}])
        self.assertEqual(group["clock_source"], "default")
        self.assertEqual(group["clocks"]["7"], "16:05-16:50")
        with self.assertRaisesRegex(ValueError, "忙碌"):
            self.invoke("activity_preview", group_token=group["token"], day=1, start=3, end=4)
        selected = self.invoke("request", text="选空档 周三 1-2节", group_token=group["token"])
        self.assertIn("第 1-2 节", selected["label"])
        self.assertFalse(selected["needs_clocks"])
        self.assertIn("08:00-09:40", selected["label"])
        self.assertEqual(selected["clock_choices"]["personal"]["1"], SCHOOL_CLOCKS[1])

        context = {"activity": selected["token"]}
        timed = self.invoke("request", text="确认组队作息 我的课表", workbench=context)
        self.assertFalse(timed["needs_clocks"])
        self.assertIn("08:00-09:40", timed["label"])
        self.assertEqual(timed["group"]["counts"], group["counts"])
        self.assertEqual(timed["group_token"], timed["group"]["token"])
        self.assertEqual(self.source.read_bytes(), original)

        draft = self.invoke("request", text="制定小组日程", workbench={"activity": selected["token"]})
        self.assertEqual((draft["draft"]["start"], draft["draft"]["end"]), ("08:00", "09:40"))
        edited = self.invoke("schedule", operation="save", token=draft["token"],
                             draft={**draft["draft"], "title": "虚构讨论", "end": "09:30"})
        self.assertEqual(edited["draft"]["end"], "09:30")
        saved = self.invoke("activity", slot=timed["token"], title="虚构讨论", export_ics=True)
        self.assertTrue(saved["updated"])
        calendar = (self.harness.exports / saved["files"][0]["id"]).read_text(encoding="utf-8")
        self.assertIn("DTSTART:20261021T000000Z", calendar)

    def test_group_clock_confirmation_preserves_custom_member_times(self):
        self.source.unlink()
        first = (time(8, 10), time(8, 50))
        member = service.make_busy_card(replace(self.tt, period_times={1: first}),
                                        "虚构组员", weeks=[7])
        prepared = self.invoke("request", text=f"查第7周共同空闲 {member.encode()}")
        group = self.invoke("request", text="确认组队", workbench={"group_prepare": prepared["token"]})
        selected = self.invoke("activity_preview", group_token=group["token"], day=2, start=1, end=2)
        self.assertTrue(selected["needs_clocks"])
        self.assertEqual(selected["clock_choices"], {})
        with self.assertRaisesRegex(ValueError, "缺少"):
            self.invoke("activity_clocks", slot=selected["token"], clocks={"3": "10:00-10:45"})
        with self.assertRaisesRegex(ValueError, "已有"):
            self.invoke("activity_clocks", slot=selected["token"], clocks={"1": "08:10-08:45", "2": "08:55-09:35"})
        with self.assertRaisesRegex(ValueError, "重叠"):
            self.invoke("activity_clocks", slot=selected["token"], clocks={"2": "08:40-09:35"})
        timed = self.invoke("activity_clocks", slot=selected["token"], clocks={"2": "08:55-09:35"})
        self.assertEqual(timed["group"]["clocks"], {"1": "08:10-08:50", "2": "08:55-09:35"})
        self.assertFalse(timed["needs_clocks"])
        self.assertEqual(self.invoke("group_refresh", token=timed["group_token"])["clocks"], timed["group"]["clocks"])
        with self.assertRaisesRegex(ValueError, "先导入"):
            self.invoke("activity", slot=timed["token"], title="虚构讨论")
        self.assertFalse(self.source.exists())
        with self.assertRaisesRegex(ValueError, "没有可采用"):
            self.invoke("request", text="确认组队作息 预设", workbench={"activity": selected["token"]})
        export = self.invoke("point_grid", token=timed["group_token"])
        page = (self.harness.exports / export["files"][0]["id"]).read_text(encoding="utf-8")
        self.assertIn("08:55-09:35", page)
        self.assertNotIn(member.name, page)

    def test_grid_pair_uses_default_school_clocks_and_never_selects_a_busy_neighbor(self):
        timetable = replace(self.tt, period_times={})
        save_source(timetable, self.source)
        card = service.make_busy_card(replace(timetable, courses=[]), "虚构组员", weeks=[7])
        card.busy[7].add(3)
        prepared = self.invoke("request", mode="group", shortcodes=[card.encode()], include_self=True)
        group = self.invoke("request", text="确认组队", workbench={"group_prepare": prepared["token"]})
        self.assertEqual(group["clocks"]["7"], SCHOOL_CLOCKS[7])
        self.assertEqual(group["clocks"]["8"], SCHOOL_CLOCKS[8])

        for period, expected in ((3, (3, 4)), (4, (3, 4)), (5, (5, 6)), (8, (7, 8)), (12, (11, 12))):
            with self.subTest(period=period):
                slot = self.invoke("activity_preview", group_token=group["token"], day=6, start=period, end=period,
                                   prefer_pair=True)
                self.assertEqual((slot["fields"]["start"], slot["fields"]["end"]), expected)
        single = self.invoke("request", text="选空档 周日第5小节", group_token=group["token"])
        self.assertEqual((single["fields"]["start"], single["fields"]["end"]), (5, 5))
        fallback = self.invoke("request", text="选空档 周一第3小节 优先连堂", group_token=group["token"])
        self.assertEqual((fallback["fields"]["start"], fallback["fields"]["end"]), (3, 3))
        self.assertIn("第 4 节有人忙", fallback["pair_note"])
        with self.assertRaisesRegex(ValueError, "忙碌"):
            self.invoke("request", text="选空档 周一第2大节", group_token=group["token"])

        selected = self.invoke("request", text="选空档 周三第7小节 优先连堂", group_token=group["token"])
        self.assertIn("第 7-8 节 16:00-17:40", selected["label"])
        self.assertFalse(selected["needs_clocks"])
        changed = self.invoke("activity_clocks", slot=selected["token"], clocks={"7": "16:05-16:50"})
        self.assertIn("第 7-8 节 16:05-17:40", changed["label"])
        self.assertEqual(changed["group"]["clock_source"], "custom")
        self.assertEqual(changed["group"]["clocks"]["8"], SCHOOL_CLOCKS[8])
        plan = self.invoke("request", text="制定小组日程", workbench={"activity": changed["token"]})
        self.assertEqual((plan["draft"]["start"], plan["draft"]["end"]), ("16:05", "17:40"))
        saved = self.invoke("activity", slot=changed["token"], title="虚构组队活动", export_ics=True)
        updated = service.load_timetable(self.source)
        self.assertEqual(updated.period_times, {})
        event = next(course for course in updated.courses if course.kind == "activity")
        self.assertEqual((event.start, event.end), (7, 8))
        calendar = (self.harness.exports / saved["files"][0]["id"]).read_text(encoding="utf-8")
        self.assertIn("DTSTART:20261021T080500Z", calendar)
        self.assertIn("DTEND:20261021T094000Z", calendar)

    def test_sidebar_import_updates_shared_timetable_only_after_confirmation(self):
        original = self.source.read_bytes()
        self.tt.term = "侧栏导入"
        incoming = self.home / "来件.yaml"
        save_source(self.tt, incoming)
        prepared = self.invoke("request", mode="import", files=[{"path": str(incoming), "name": incoming.name}])
        preview = self.invoke("preview", token=prepared["token"])
        self.assertTrue(preview["overwrite"])
        self.assertEqual(self.source.read_bytes(), original)
        saved = self.invoke("commit", token=preview["confirmation"])
        self.assertTrue(saved["updated"])
        self.assertEqual(saved["files"], [])
        self.assertEqual(service.load_timetable(self.source).term, self.tt.term)
        undo = self.invoke("status", full=True)["undo"]
        self.assertEqual(undo["label"], "导入课表")
        self.invoke("undo", token=undo["token"])
        self.assertEqual(self.source.read_bytes(), original)

    def test_undo_first_import_restores_the_empty_start(self):
        incoming = self.home / "导入样例.yaml"
        self.source.rename(incoming)
        prepared = self.invoke("request", mode="import", files=[{"path": str(incoming), "name": incoming.name}])
        preview = self.invoke("preview", token=prepared["token"])
        self.invoke("commit", token=preview["confirmation"])
        undo = self.invoke("status", full=True)["undo"]
        self.invoke("undo", token=undo["token"])
        status = self.invoke("status", full=True)
        self.assertFalse(status["present"])
        self.assertIsNone(status["undo"])
        self.assertTrue(incoming.is_file())

    def test_bundled_example_supports_the_release_guide(self):
        self.source.unlink()
        sample = Path(__file__).resolve().parents[1] / "examples" / "插件示例课表.yaml"
        prepared = self.invoke("request", mode="import", files=[{"path": str(sample), "name": sample.name}])
        preview = self.invoke("preview", token=prepared["token"])
        self.assertEqual(preview["conflicts"], [])
        self.assertFalse(self.source.exists())
        self.invoke("commit", token=preview["confirmation"])
        original = self.source.read_bytes()

        prepared = self.invoke("request", text="把第7周周二的体育课调到周五第4大节\uff0c地点不变")
        preview = self.invoke("preview", token=prepared["token"])
        self.assertEqual(preview["conflicts"], [])
        self.invoke("commit", token=preview["confirmation"])
        courses = service.week_calendar_data(service.load_timetable(self.source), 7)["courses"]
        sport = next(course for course in courses if course.name == "体育\uff08篮球\uff09")
        self.assertEqual((sport.day, sport.start, sport.end, sport.room), (4, 7, 8, "示例操场"))

        undo = self.invoke("status", full=True)["undo"]
        self.invoke("undo", token=undo["token"])
        self.assertEqual(self.source.read_bytes(), original)

    def test_weekly_lookup_works_without_semester_date(self):
        self.tt.semester_start = None
        self.tt.weeks_total = 12
        save_source(self.tt, self.source)
        result = self.invoke("request", text="查第7周的课")
        self.assertEqual(result["week"], 7)
        self.assertEqual(result["weeks_total"], 12)
        self.assertEqual(result["days"][1]["courses"][0]["name"], "体育")
        self.assertFalse(result["days"][1]["date"])
        self.assertEqual(self.invoke("request", mode="agenda", week=12)["week"], 12)
        with self.assertRaisesRegex(ValueError, "不在学期内"):
            self.invoke("request", mode="agenda", week=13)

    def test_set_current_week_updates_on_local_monday_and_can_be_undone(self):
        class Clock(datetime):
            instant = datetime(2026, 11, 15, 15, 59, tzinfo=timezone.utc)

            @classmethod
            def now(cls, tz=None):
                return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)

        self.tt.semester_start = None
        save_source(self.tt, self.source)
        original = self.source.read_bytes()
        with patch("courseflow.harness.datetime", Clock):
            form = self.invoke("semester_week")
            self.assertEqual(form["today"], "2026-11-15")
            self.assertEqual(form["monday"], "2026-11-09")
            self.assertIsNone(form["current_week"])
            self.assertEqual(self.source.read_bytes(), original)
            with self.assertRaisesRegex(ValueError, "请输入 1 到 16"):
                self.invoke("save_semester_week", token=form["token"], week=17)
            saved = self.invoke("save_semester_week", token=form["token"], week=7)
            self.assertTrue(saved["updated"])
            updated = service.load_timetable(self.source)
            self.assertEqual(updated.semester_start, date(2026, 9, 28))
            self.assertEqual(updated.period_times, self.tt.period_times)
            sunday = self.invoke("status", full=True)
            self.assertEqual(sunday["week"], 7)
            Clock.instant = datetime(2026, 11, 15, 16, tzinfo=timezone.utc)
            self.assertEqual(sunday["next_day_at"], int(Clock.instant.timestamp() * 1_000))
            monday = self.invoke("status", full=True)
            self.assertEqual((monday["date"], monday["week"]), ("2026-11-16", 8))
            self.assertEqual(self.invoke("semester_week")["current_week"], 8)
            self.invoke("undo", token=monday["undo"]["token"])
        self.assertEqual(self.source.read_bytes(), original)

    def test_setting_current_week_rejects_an_outdated_form(self):
        form = self.invoke("semester_week")
        self.tt.term = "桌面版刚刚修改"
        service.save_timetable(self.tt, self.source)
        with self.assertRaisesRegex(ValueError, "已更新"):
            self.invoke("save_semester_week", token=form["token"], week=7)
        self.assertEqual(service.load_timetable(self.source).term, self.tt.term)

    def test_wallpaper_export_reuses_custom_background_at_confirmation(self):
        original = self.source.read_bytes()
        image = BytesIO()
        Image.new("RGB", (160, 90), (60, 160, 240)).save(image, format="PNG")
        background = {"name": "我的背景.png", "base64": base64.b64encode(image.getvalue()).decode("ascii")}
        wallpaper = {"background": "custom", "image": background}
        with patch("courseflow.service.import_image") as recognize:
            prepared = self.invoke("request", mode="export", formats=["desktop", "phone"], wallpaper=wallpaper)
            recognize.assert_not_called()
        self.assertEqual(prepared["wallpaper_background"], background["name"])
        with patch("courseflow.render.desktop_size", return_value=(800, 600)):
            preview = Harness().run("preview", {"token": prepared["token"]})
        self.assertEqual(preview["wallpaper_background"], background["name"])
        self.assertEqual(list(preview["wallpaper_previews"]), ["desktop", "phone"])
        self.assertFalse(self.harness.exports.exists())
        self.assertEqual(self.source.read_bytes(), original)
        with patch("courseflow.render.desktop_size", return_value=(800, 600)):
            saved = Harness().run("commit", {"token": preview["confirmation"]})
        self.assertEqual(len(saved["files"]), 2)
        for fmt, file in zip(("desktop", "phone"), saved["files"]):
            raw_preview = base64.b64decode(preview["wallpaper_previews"][fmt])
            with Image.open(self.harness.exports / file["id"]) as wallpaper_image, Image.open(BytesIO(raw_preview)) as thumb:
                self.assertEqual(wallpaper_image.getpixel((0, 0)), (37, 99, 148))
                wallpaper_image.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
                self.assertEqual(thumb.size, wallpaper_image.size)
                difference = ImageChops.difference(thumb, wallpaper_image)
                self.assertLess(max(ImageStat.Stat(difference).mean), 4)
        self.assertEqual(self.source.read_bytes(), original)

    def test_wallpaper_export_uses_selected_preset(self):
        prepared = self.invoke("request", mode="export", formats=["desktop"], wallpaper={"background": "sea"})
        preview = self.invoke("preview", token=prepared["token"])
        self.assertEqual(preview["wallpaper_background"], BACKGROUNDS["sea"])
        self.assertEqual(list(preview["wallpaper_previews"]), ["desktop"])
        size = (800, 600)
        with patch("courseflow.render.desktop_size", return_value=size):
            saved = self.invoke("commit", token=preview["confirmation"])
        with Image.open(self.harness.exports / saved["files"][0]["id"]) as wallpaper_image:
            self.assertEqual(wallpaper_image.getpixel((0, 0)), make_background("sea", size).getpixel((0, 0)))

    def test_wallpaper_background_preview_uses_selected_preset_and_dimensions(self):
        original = self.source.read_bytes()
        size = (960, 540)
        with patch("courseflow.render.desktop_size", return_value=(1920, 1080)):
            for background in BACKGROUNDS:
                with self.subTest(background=background):
                    preview = self.invoke("wallpaper_background_preview", background=background, format="desktop")
                    with Image.open(BytesIO(base64.b64decode(preview["base64"]))) as image:
                        self.assertEqual(image.size, size)
                        self.assertEqual(image.getpixel((0, 0)), make_background(background, size).getpixel((0, 0)))
        portrait = self.invoke("wallpaper_background_preview", background="night", format="phone")
        with Image.open(BytesIO(base64.b64decode(portrait["base64"]))) as image:
            self.assertEqual(image.size, (432, 960))
        self.assertFalse(self.harness.exports.exists())
        self.assertFalse(self.harness.drafts.exists())
        self.assertEqual(self.source.read_bytes(), original)

    def test_image_requires_verified_api_before_recognition(self):
        image = self.home / "example.png"
        image.write_bytes(b"test")
        with patch("courseflow.service.ai_settings", return_value=AIConfig()), patch("courseflow.service.import_image") as recognize:
            with self.assertRaises(SettingsRequired):
                self.invoke("request", text="导出课表", files=[{"path": str(image), "name": image.name}])
            recognize.assert_not_called()

    def test_command_adjustment_can_select_confirm_and_undo_without_writing_early(self):
        original = self.source.read_bytes()
        result = self.invoke("request", text="把第7周的体育课调到周六第1大节")
        context = {"prepared": result["token"]}
        preview = self.invoke("request", text="预览调课", workbench=context)
        self.assertEqual(len(preview["candidates"]), 2)
        context["candidates"] = [item["id"] for item in preview["candidates"]]
        preview = self.invoke("request", text="选课次 2", workbench=context)
        context["confirmation"] = preview["confirmation"]
        self.assertEqual(self.source.read_bytes(), original)
        with self.assertRaisesRegex(ValueError, "确认调课"):
            self.invoke("request", text="确认导出", workbench=context)
        self.assertTrue(self.invoke("request", text="确认调课", workbench=context)["updated"])
        self.assertNotEqual(self.source.read_bytes(), original)
        self.assertTrue(self.invoke("request", text="撤销上一步")["updated"])
        self.assertEqual(self.source.read_bytes(), original)

    def test_command_reserving_todo_respects_busy_slots_even_without_self_in_group(self):
        original = self.source.read_bytes()
        todo = self.invoke("request", text="添加待做任务 2026-10-23前交实验报告")["items"][0]
        done = self.invoke("request", text="完成待办 交实验报告")
        self.assertTrue(done["items"][0]["done"])
        reopened = self.invoke("request", text="重新打开待办 交实验报告")
        self.assertFalse(reopened["items"][0]["done"])
        card = service.make_busy_card(replace(self.tt, courses=[]), "虚构组员", [7])
        prepared = self.invoke("request", text=f"查第7周共同空闲 {card.encode()}")
        group = self.invoke("request", text="确认组队", workbench={"group_prepare": prepared["token"]})
        reserve = self.invoke("request", text="给待办 交实验报告 留出时间", group_token=group["token"])
        self.assertEqual(reserve["item"]["id"], todo["id"])
        context = {"todo_id": todo["id"]}
        clash = self.invoke("request", text="选空档 周二 3-4节", group_token=group["token"], workbench=context)
        with self.assertRaisesRegex(ValueError, "重叠"):
            self.invoke("request", text="确认留出时间", workbench={"activity": clash["token"]})
        self.assertEqual(self.source.read_bytes(), original)
        free = self.invoke("request", text="选空档 周三 1-2节", group_token=group["token"], workbench=context)
        saved = self.invoke("request", text="确认添加活动 地点:虚构研讨室 并导出日历", workbench={"activity": free["token"]})
        self.assertTrue(saved["updated"])
        self.assertTrue(saved["files"][0]["name"].endswith(".ics"))
        activity = next(course for course in service.load_timetable(self.source).courses if course.kind == "activity")
        self.assertEqual((activity.name, activity.day, activity.start, activity.room), (todo["title"], 2, 1, "虚构研讨室"))
        self.assertFalse(self.invoke("request", text="查看待办")["items"][0]["done"])

    def test_command_manual_group_schedule_and_card(self):
        original = self.source.read_bytes()
        card = service.make_busy_card(replace(self.tt, courses=[]), "甲", [7])
        ready = self.invoke("request", text=f"查第7周空闲 {card.encode()}")
        group = self.invoke("request", text="确认组队 第7周", workbench={"group_prepare": ready["token"]})
        chosen = self.invoke("request", text="选空档 周三 1-2节", group_token=group["token"])
        result = self.invoke("request", text="制定小组日程", workbench={"activity": chosen["token"]})
        for line in ("设置日程 事项:虚构讨论 | 地点:研讨室 | 结束:08:40", "添加议程 10 | 复盘错题", "添加分工 甲 | 准备例题"):
            result = self.invoke("request", text=line, schedule_token=result["token"])
        self.assertEqual(result["draft"]["end"], "08:40")
        self.assertEqual(result["draft"]["agenda"][0]["minutes"], 10)
        self.assertEqual(result["draft"]["prep"][0]["owners"], ["甲"])
        result = self.invoke("request", text="预览日程卡 简洁清单", schedule_token=result["token"])
        self.assertEqual(result["style"], "simple")
        result = self.invoke("request", text="导出日程卡 简洁清单", schedule_token=result["token"])
        self.assertTrue(result["files"][0]["name"].endswith("简洁清单.png"))
        self.assertEqual(self.source.read_bytes(), original)

    def test_command_view_controls_settings_and_semester_confirmation(self):
        week = self.invoke("request", text="周课表网格", workbench={"agenda_week": 7})
        self.assertEqual((week["week"], week["view_mode"]), (7, "week"))
        self.assertEqual(self.invoke("request", text="下一周", workbench={"agenda_week": 7})["week"], 8)
        self.assertEqual(self.invoke("request", text="刷新课表")["view"], "agenda")
        self.assertEqual(self.invoke("request", text="打开 AI 接口设置")["type"], "settings")
        with patch("courseflow.service.ai_settings", return_value=AIConfig()), self.assertRaises(SettingsRequired):
            self.invoke("request", text="自检 AI 接口")
        original = self.source.read_bytes()
        week = self.invoke("request", text="设置当前周次 7")
        self.assertEqual(week["suggested_week"], 7)
        self.assertEqual(self.source.read_bytes(), original)
        saved = self.invoke("request", text="确认周次", workbench={"semester": week["token"], "suggested_week": 7})
        self.assertEqual(saved["type"], "saved")

    def test_command_wallpaper_background_and_export_share_confirmation(self):
        picture = self.home / "background.png"
        Image.new("RGB", (20, 20), (20, 30, 40)).save(picture)
        source = self.source.read_bytes()
        with patch.object(Harness, "require_vision") as vision:
            prepared = self.invoke("request", text="导出手机壁纸 用附件作为壁纸背景",
                                   files=[{"path": str(picture), "name": picture.name}])
            vision.assert_not_called()
        self.assertEqual(prepared["wallpaper_background"], picture.name)
        preview = self.invoke("request", text="预览导出", workbench={"prepared": prepared["token"]})
        self.assertEqual(list(preview["wallpaper_previews"]), ["phone"])
        with patch("courseflow.render.PHONE_SIZE", (640, 1024)):
            exported = self.invoke("request", text="确认导出", workbench={"confirmation": preview["confirmation"]})
        self.assertTrue(exported["files"][0]["name"].endswith(".png"))
        self.assertEqual(self.source.read_bytes(), source)


if __name__ == "__main__":
    unittest.main()
