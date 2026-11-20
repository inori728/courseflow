import base64
from datetime import date, datetime, timezone
from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageChops

from courseflow import service
from courseflow.group import BusyCard
from courseflow.harness import Harness, SettingsRequired
from courseflow.model import Change, Course, Timetable
from courseflow.planning import require_free
from courseflow.semester import SCHOOL_CLOCKS
from courseflow.settings import AIConfig
from courseflow.source import save_source


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = datetime(2026, 11, 15, 23, 30, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


class PlanningWorkflowTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.home = Path(folder.name)
        self.source = self.home / "课表.yaml"
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, {"COURSEFLOW_HOME": str(self.home), "COURSEFLOW_SOURCE": str(self.source)}).start()
        self.app = Harness()
        self.start = date(2026, 11, 16)
        self.tt = service.configure_semester(Timetable(), "虚构学期", self.start, 4, SCHOOL_CLOCKS)

    def group(self, busy=(), minutes=0):
        member = BusyCard("甲", self.start, {1: set(busy)}, self.tt.period_times)
        prepared = self.app.run("request", {"text": f"查共同空闲 {member.encode()}"})
        return self.app.run("group_search", {"token": prepared["token"], "members": [{"name": "甲"}],
                                             "week": 1, "minimum": 1, "minutes": minutes})

    def edit(self, operation, view, **fields):
        return Harness().run("schedule", {"operation": operation, "token": view["token"], **fields})

    def test_minutes_allow_short_transitions_and_reject_long_gaps(self):
        member = BusyCard("甲", self.start, {1: set()}, self.tt.period_times)
        result = service.group_free([member], 1, 1)
        self.assertEqual(require_free(result, {"date": "2026-11-16", "start": "08:22", "end": "09:22"}), 60)
        with self.assertRaisesRegex(ValueError, "全员空档"):
            require_free(result, {"date": "2026-11-16", "start": "11:15", "end": "14:20"})
        result = self.group(set(range(84)) - {3, 4}, minutes=60)
        self.assertEqual(result["windows"], [])

    def test_next_named_course_uses_actual_occurrences_and_partial_clock_reminders(self):
        self.tt.courses = [
            Course("数据结构", 0, 1, 2, "旧地点", "1-4周", skip=[1],
                   changes=[Change(2, day=1, start=3, end=4, room="新地点", target_week=1)]),
            Course("数据结构实验", 0, 5, 6, "实验室", "1周"),
        ]
        self.tt.period_times = {5: self.tt.period_times[5]}
        save_source(self.tt, self.source)
        with patch("courseflow.harness.datetime", FixedClock):
            response = self.app.run("request", {"text": "下次数据结构在哪上"})
            self.assertEqual(response["upcoming"]["date"], "2026-11-17")
            self.assertEqual(response["upcoming"]["room"], "新地点")
            self.assertIn("3-4 节", response["message"])
            response = self.app.run("request", {"text": "下次数据在哪上"})
            self.assertIn("多门课", response["message"])
            upcoming = self.app.run("status", {"full": True})["upcoming"]
        self.assertEqual(upcoming["name"], "数据结构实验")
        self.assertGreater(upcoming["startsAt"], FixedClock.now(timezone.utc).timestamp() * 1000)

    def test_todos_are_independent_of_timetable_and_reserve_verified_activity(self):
        with patch("courseflow.harness.local_today", return_value=self.start):
            response = self.app.run("request", {"text": "添加待办 周五前交实验报告"})
        todo = response["items"][0]
        self.assertEqual((todo["title"], todo["due"]), ("交实验报告", "2026-11-20"))
        self.assertFalse(self.source.exists())
        save_source(self.tt, self.source)
        group = self.group()
        saved = self.app.run("activity", {"token": group["token"], "day": 0, "start": 1, "end": 1, "title": todo["title"]})
        self.assertTrue(saved["updated"])
        self.assertEqual(service.load_timetable(self.source).courses[0].kind, "activity")
        complete = self.app.run("todos", {"operation": "complete", "id": todo["id"], "done": True})
        self.assertTrue(complete["items"][0]["done"])
        result = self.app.run("request", {"text": "删除待办 交实验报告"})
        self.assertEqual(result["items"], [])
        self.assertEqual(len(service.load_timetable(self.source).courses), 1)

    def test_chat_candidates_require_shortening_confirmation(self):
        group = self.group()
        request = {"text": "约一人做例题, 连续60分钟", "group_token": group["token"]}
        conditions = {"title": "复习例题", "minutes": 60, "participant_count": 1, "preferred_date": "2026-11-16",
                      "preferred_start": "08:00", "preferred_end": "08:35", "deadline": "2026-11-17T18:00"}
        with self.assertRaises(SettingsRequired):
            self.app.run("request", request)
        config = AIConfig(base_url="http://127.0.0.1:1/v1", model="test-model")
        with patch.object(self.app, "require_vision", return_value=config), patch("courseflow.planning.AIClient.json", return_value=conditions), \
                patch("courseflow.harness_planning.datetime", FixedClock):
            choices = self.app.run("request", request)
        self.assertEqual(choices["options"][0]["date"], "2026-11-17")
        short = next(index for index, option in enumerate(choices["options"]) if option["kind"] == "shorter")
        refused = self.edit("choose", choices, index=short)
        self.assertEqual(refused["type"], "schedule_options")
        accepted = self.edit("choose", choices, index=short, confirm_shorter=True)
        self.assertEqual((accepted["draft"]["start"], accepted["draft"]["end"]), ("08:00", "08:35"))
        chosen = self.app.run("request", {"text": "选方案 A\uff0c地点定在虚构研讨室", "schedule_token": choices["token"]})
        self.assertEqual(chosen["draft"]["room"], "虚构研讨室")

    def test_review_edit_undo_and_both_card_styles(self):
        group = self.group()
        current = self.app.run("schedule", {"operation": "start", "group_token": group["token"], "day": 0, "first": 1, "last": 2})
        initial = self.edit("save", current, draft={"title": "例题复习", "room": "虚构研讨室", "start": "08:10", "end": "09:10",
                        "agenda": [{"title": "复盘", "minutes": 15}], "prep": [{"title": "带例题", "owners": ["甲"]}]})
        result = {"agenda": [{"title": "保留复盘", "minutes": 10}],
                  "prep": [{"title": "错题放到会前", "owners": ["全员"]}], "summary": "活动缩短, 先准备错题."}
        config = AIConfig(base_url="http://127.0.0.1:1/v1", model="test-model")
        with patch.object(Harness, "require_vision", return_value=config), \
                patch("courseflow.planning.AIClient.json", return_value={"start": "11:30", "end": "14:30"}) as ai:
            with self.assertRaisesRegex(ValueError, "全员空档"):
                self.edit("revise", initial, text="改到跨午休的时段")
            self.assertEqual(ai.call_count, 1)
        with patch.object(Harness, "require_vision", return_value=config), \
                patch("courseflow.planning.AIClient.json", side_effect=[{"start": "08:55", "end": "09:30"}, result]):
            review = self.edit("revise", initial, text="改成35分钟并保留10分钟复盘")
        self.assertEqual(review["review"]["draft"]["end"], "09:30")
        self.assertEqual(review["draft"], initial["draft"])
        with self.assertRaisesRegex(ValueError, "全员空档"):
            self.edit("apply", review, draft={"start": "11:30", "end": "14:30"})
        applied = self.edit("apply", review, draft={"notes": "手动补充说明"})
        self.assertEqual(applied["draft"]["room"], "虚构研讨室")
        styles = []
        for style in ("green", "simple"):
            preview = self.edit("preview", applied, style=style)
            self.assertEqual(preview["draft"], applied["draft"])
            with Image.open(BytesIO(base64.b64decode(preview["preview"]))) as image:
                self.assertEqual(image.format, "PNG")
            card = self.edit("export", preview, style=style)
            self.assertEqual(card["draft"], applied["draft"])
            with Image.open(self.app.exports / card["files"][0]["id"]) as image:
                self.assertEqual(image.format, "PNG")
                styles.append(image.copy())
        self.assertEqual(styles[0].size, styles[1].size)
        self.assertIsNotNone(ImageChops.difference(*styles).getbbox())
        undone = self.edit("undo", applied)
        self.assertEqual(undone["draft"], initial["draft"])
        self.assertFalse(self.source.exists())

    def test_suggest_from_one_request_with_blank_schedule_fields(self):
        group = self.group()
        blank = self.app.run("schedule", {"operation": "start", "group_token": group["token"],
                                          "day": 0, "first": 7, "last": 8})
        self.assertEqual([blank["draft"][key] for key in ("title", "room", "notes")], ["", "", ""])
        request = "在虚构研讨室彩排项目汇报, 重点检查演示."
        response = {
            "title": "项目汇报彩排", "room": "虚构研讨室", "notes": "重点检查演示",
            "agenda": [{"title": "完整彩排", "minutes": 40}],
            "prep": [{"title": "准备演示文件", "owners": ["甲"]}], "summary": "安排彩排和演示检查.",
            "date": "2026-12-20", "start": "12:30", "end": "13:30", "members": ["虚构其他人"],
        }
        config = AIConfig(base_url="http://127.0.0.1:1/v1", model="test-model")
        with patch.object(Harness, "require_vision", return_value=config), \
                patch("courseflow.planning.AIClient.json", return_value=response) as ai:
            review = self.edit("suggest", blank, text=request)
            commanded = self.app.run("request", {"text": f"拟议程 {request}", "schedule_token": blank["token"]})
            self.assertEqual(ai.call_count, 2)
        self.assertEqual(review["review"]["draft"], commanded["review"]["draft"])
        self.assertEqual(review["draft"], blank["draft"])
        proposal = review["review"]["draft"]
        for key in ("date", "start", "end", "members"):
            self.assertEqual(proposal[key], blank["draft"][key])
        for key in ("title", "room", "notes", "agenda", "prep"):
            self.assertEqual(proposal[key], response[key])
        self.assertEqual(self.edit("discard", review)["draft"], blank["draft"])
        applied = self.edit("apply", review)
        self.assertEqual(applied["draft"], proposal)
        self.assertEqual(self.edit("undo", applied)["draft"], blank["draft"])
        self.assertFalse(self.source.exists())

    def test_suggest_preserves_written_fields_and_checks_generated_fields(self):
        group = self.group()
        blank = self.app.run("schedule", {"operation": "start", "group_token": group["token"],
                                          "day": 0, "first": 1, "last": 2})
        manual = self.edit("save", blank, draft={"title": "手填的事项", "notes": "手填的说明"})
        response = {"title": "建议事项", "notes": "建议说明", "room": "凭空加入的地点",
                    "agenda": [{"title": "核对讲稿", "minutes": 30}], "prep": []}
        config = AIConfig(base_url="http://127.0.0.1:1/v1", model="test-model")
        with patch.object(Harness, "require_vision", return_value=config), \
                patch("courseflow.planning.AIClient.json", return_value=response):
            suggestion = self.edit("suggest", manual, text="重点检查讲稿")
        draft = suggestion["review"]["draft"]
        self.assertEqual((draft["title"], draft["notes"], draft["room"]), ("手填的事项", "手填的说明", ""))
        with patch.object(Harness, "require_vision", return_value=config):
            missing_title = {"agenda": [], "prep": []}
            with patch("courseflow.planning.AIClient.json", return_value=missing_title):
                with self.assertRaisesRegex(ValueError, "AI 未能生成事项"):
                    self.edit("suggest", blank, text="检查讲稿")
            long_agenda = {**response, "agenda": [{"title": "超时议程", "minutes": 101}]}
            with patch("courseflow.planning.AIClient.json", return_value=long_agenda):
                with self.assertRaisesRegex(ValueError, "现场议程超过"):
                    self.edit("suggest", blank, text="检查讲稿")


if __name__ == "__main__":
    unittest.main()
