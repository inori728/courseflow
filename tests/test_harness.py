import base64
from datetime import date, datetime, timezone
from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

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
        preview = Harness().run("preview", {"token": prepared["token"]})
        self.assertEqual(preview["wallpaper_background"], background["name"])
        self.assertFalse(self.harness.exports.exists())
        with patch("courseflow.render.desktop_size", return_value=(800, 600)):
            saved = Harness().run("commit", {"token": preview["confirmation"]})
        self.assertEqual(len(saved["files"]), 2)
        for file in saved["files"]:
            with Image.open(self.harness.exports / file["id"]) as wallpaper_image:
                self.assertEqual(wallpaper_image.getpixel((0, 0)), (37, 99, 148))
        self.assertEqual(self.source.read_bytes(), original)

    def test_wallpaper_export_uses_selected_preset(self):
        prepared = self.invoke("request", mode="export", formats=["desktop"], wallpaper={"background": "sea"})
        preview = self.invoke("preview", token=prepared["token"])
        self.assertEqual(preview["wallpaper_background"], "海盐渐变")
        size = (800, 600)
        with patch("courseflow.render.desktop_size", return_value=size):
            saved = self.invoke("commit", token=preview["confirmation"])
        with Image.open(self.harness.exports / saved["files"][0]["id"]) as wallpaper_image:
            self.assertEqual(wallpaper_image.getpixel((0, 0)), make_background("sea", size).getpixel((0, 0)))

    def test_wallpaper_background_preview_uses_selected_preset_and_dimensions(self):
        original = self.source.read_bytes()
        size = (960, 540)
        with patch("courseflow.harness.desktop_size", return_value=(1920, 1080)):
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


if __name__ == "__main__":
    unittest.main()
