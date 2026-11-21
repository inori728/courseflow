"""Regression coverage for the shared assistant and its workbench confirmations."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

from courseflow import service
from courseflow.guide import usage_guide
from courseflow.harness import Harness, SettingsRequired
from courseflow.model import Course, Timetable
from courseflow.semester import SCHOOL_CLOCKS
from courseflow.settings import AIConfig
from courseflow.source import save_source
from courseflow.todos import todo_list


class AssistantTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "虚构课表.yaml"
        environment = patch.dict("os.environ", {"COURSEFLOW_HOME": str(self.root)})
        environment.start()
        self.addCleanup(environment.stop)
        course = Course("虚构体育", 1, 1, 2, "示例场馆", "1-16周")
        self.tt = service.configure_semester(Timetable(courses=[course]), "虚构学期", date(2026, 9, 7), 16,
                                             SCHOOL_CLOCKS)
        save_source(self.tt, self.source)
        self.workbench = Harness(self.source)
        self.original = self.source.read_bytes()
        self.config = AIConfig(base_url="http://127.0.0.1:1/v1", model="assistant-test")
        self.config.verified_signature = self.config.signature

    def send(self, text, intent, mode="operate", **payload):
        with patch("courseflow.service.ai_settings", return_value=self.config), \
                patch("courseflow.assistant.AIClient.json", return_value=intent):
            return self.workbench.run("assistant", {"mode": mode, "text": text, **payload})

    def test_local_help_and_unconfigured_send_make_no_model_request(self):
        with patch("courseflow.service.ai_settings", return_value=AIConfig()), \
                patch("courseflow.assistant.AIClient.json") as model:
            self.assertFalse(self.workbench.run("settings", {})["verified"])
            guide = self.workbench.run("guide", {})
            command = self.workbench.run("request", {"text": "帮助"})
            self.assertEqual(guide, command)
            self.assertEqual([section["title"] for section in guide["sections"]], ["命令", "助手如何使用", "常用功能"])
            layout = guide["sections"][1]["layout"]
            self.assertEqual([item["title"] for item in layout["notes"]], ["聊天", "课表操作", "AI 设置"])
            self.assertEqual([item["title"] for item in layout["examples"]],
                             ["查课", "导入课表", "往课表加安排", "调课", "组队找空闲", "小组日程卡",
                              "待办", "给待办留时间", "手机壁纸"])
            self.assertTrue(all(item["text"] for item in layout["examples"]))
            self.assertEqual(layout["examples"][1]["hint"], "附一张课表截图\u3002")
            self.assertIn("能按天给我看看下个星期要上什么课吗", usage_guide(commands=False)["message"])
            self.assertNotIn("参考例句", usage_guide(commands=False, examples=False)["message"])
            self.assertEqual(self.workbench.run("request", {"text": "助手"})["view"], "assistant")
            with self.assertRaises(SettingsRequired):
                self.workbench.run("assistant", {"mode": "operate", "text": "导入截图",
                                                "files": [{"name": "示例.png", "base64": "未读取的附件"}]})
            model.assert_not_called()
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_chat_and_unknown_intents_never_dispatch_workbench_actions(self):
        result = self.send("帮我添加待办", {"message": "请切换模式", "action": "todo", "operation": "add",
                                         "title": "不能写入"}, mode="chat")
        self.assertNotIn("result", result)
        self.assertEqual(todo_list({})["items"], [])
        self.assertNotIn("result", self.send("无关内容", {"action": "commit"}))
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_weekly_queries_tolerate_model_fields_and_use_the_requested_week(self):
        cases = (
            ("帮我看看下周有哪些课\uff0c按星期列一下\uff0c带上上课时间和教室\u3002", {"when": "next_week"}, 12),
            ("查第 13 周的课表\uff0c按星期列出课程\u3001上课时间和教室\u3002", {"when": "week", "week": "13"}, 13),
            ("帮我翻一下第十三周的课程安排", {"when": "weekly", "week": 12}, 13),
            ("我想看看下星期的上课安排", {"when": "week"}, 12),
            ("就看我们刚才说的那一周", {"week": "第 13 周"}, 13),
            ("就看我们刚才说的那一周", {"when": "week", "week": "13"}, 13),
            ("就看我们刚才说的那一周", {"when": "next_week"}, 12),
        )
        with patch("courseflow.harness_commands.local_today", return_value=date(2026, 11, 21)):
            for text, intent, week in cases:
                with self.subTest(text=text, intent=intent):
                    reply = self.send(text, {"action": "agenda", **intent})
                    self.assertIn("result", reply)
                    self.assertEqual(reply["result"]["week"], week)
                    self.assertIn("周二 08:00-09:40 · 虚构体育 · 示例场馆", reply["message"])
        unclear = self.send("帮我查查课表", {"action": "agenda", "when": "week"})
        self.assertNotIn("result", unclear)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_week_scope_is_preserved_when_model_selects_a_day_or_single_lesson(self):
        self.tt.courses.append(Course("虚构程序设计", 4, 3, 4, "示例教室", "1-16周"))
        save_source(self.tt, self.source)
        saved = self.source.read_bytes()
        day = date(2026, 11, 21)
        cases = (
            ("帮我看看下周有哪些课\uff0c按星期列一下\uff0c带上上课时间和教室\u3002", "next", 12),
            ("给我看看下星期的课程安排", "下一节", 12),
            ("能按天给我看看下个星期要上什么课吗", "next", 12),
            ("查第 13 周的课表", "today", 13),
            ("下一周的课都有哪些", "tomorrow", 12),
        )
        with patch("courseflow.harness.local_today", return_value=day), \
                patch("courseflow.harness_commands.local_today", return_value=day):
            for text, when, week in cases:
                with self.subTest(text=text, when=when):
                    reply = self.send(text, {"action": "agenda", "when": when})
                    self.assertEqual(reply["result"].get("week"), week)
                    self.assertEqual(sum(bool(item["courses"]) for item in reply["result"]["days"]), 2)
                    self.assertIn("周二 08:00-09:40 · 虚构体育 · 示例场馆", reply["message"])
                    self.assertIn("周五 10:00-11:40 · 虚构程序设计 · 示例教室", reply["message"])
            upcoming = self.send("下周开始前看看下一节课在哪儿", {"action": "agenda", "when": "next"})["result"]
            self.assertEqual(upcoming["upcoming"]["name"], "虚构体育")
            tomorrow = self.send("我想看看这周明天的课", {"action": "agenda", "when": "tomorrow"})["result"]
            self.assertTrue(tomorrow["message"].startswith("2026-11-22"))
        self.assertEqual(self.source.read_bytes(), saved)

    def test_adjustment_and_import_require_explicit_preview_confirmation(self):
        notice = "把第7周周二的虚构体育调到周五第4大节"
        preview = self.send("第七周周二那节虚构体育要挪到同周周五第七至第八小节, 先看看怎么改",
                            {"action": "adjust", "notice": notice})["result"]
        self.assertTrue(preview["confirmation"])
        self.assertIn("周五", preview["rows"][0]["after"])
        self.assertEqual(self.source.read_bytes(), self.original)
        with self.assertRaisesRegex(ValueError, "切到课表操作"):
            self.workbench.run("assistant_choose", {"mode": "chat", "token": preview["confirmation"], "index": 0})
        self.workbench.run("commit", {"token": preview["confirmation"]})
        self.assertNotEqual(self.source.read_bytes(), self.original)
        self.workbench.run("request", {"text": "撤销上一步"})
        self.assertEqual(self.source.read_bytes(), self.original)
        example = self.root / "新课表.yaml"
        save_source(self.tt, example)
        imported = self.send("把附件里的安排整理进我的课表, 我想先校对", {"action": "import"},
                             files=[{"name": example.name, "path": str(example)}])["result"]
        self.assertEqual(imported["type"], "prepare")
        self.assertTrue(self.workbench.run("preview", {"token": imported["token"]})["confirmation"])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_assistant_previews_and_saves_a_custom_activity(self):
        with patch("courseflow.assistant.local_today", return_value=date(2026, 11, 21)):
            reply = self.send("今天第七到第八节帮我空出来做社团海报",
                              {"action": "add_entry", "title": "社团海报制作", "kind": "activity",
                               "when": "today", "periods": ["7", "8"], "room": "美工室"})
        preview = reply["result"]
        self.assertEqual(preview["write_label"], "新增活动")
        self.assertIn("2026-11-21 周六 第 7-8 节 16:00-17:40", preview["rows"][0]["after"])
        self.assertEqual(self.source.read_bytes(), self.original)
        saved = self.workbench.run("commit", {"token": preview["confirmation"]})
        self.assertTrue(saved["updated"])
        self.assertEqual(saved, self.workbench.run("commit", {"token": preview["confirmation"]}))
        updated = service.load_timetable(self.source)
        self.assertEqual(len(updated.courses), 2)
        added = next(course for course in updated.courses if course.name == "社团海报制作")
        self.assertEqual((added.kind, added.day, added.start, added.end, added.weeks, added.room),
                         ("activity", 5, 7, 8, "11周", "美工室"))
        result = self.workbench.run("request", {"text": "撤销上一步"})
        self.assertIn("新增活动", result["message"])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_assistant_adds_one_makeup_class_and_matches_exact_clock_ranges(self):
        with patch("courseflow.assistant.local_today", return_value=date(2026, 10, 19)):
            activity = self.send("把明天下午四点到五点四十记成面试准备",
                                 {"action": "add_entry", "title": "面试准备", "when": "tomorrow",
                                  "start_time": "16:00", "end_time": "17:40"})["result"]
            lesson = self.send("下周礼拜五三四节有一堂统计学补课, 加到课表",
                               {"action": "add_entry", "title": "统计学补课", "kind": "course",
                                "week": "next", "day": 5, "periods": [3, 4]})["result"]
        self.assertIn("2026-10-20 周二 第 7-8 节", activity["rows"][0]["after"])
        self.assertIn("2026-10-30 周五 第 3-4 节", lesson["rows"][0]["after"])
        self.assertEqual(lesson["write_label"], "新增课程")
        self.assertEqual(self.source.read_bytes(), self.original)
        self.workbench.run("commit", {"token": lesson["confirmation"]})
        added = next(course for course in service.load_timetable(self.source).courses if course.name == "统计学补课")
        self.assertEqual((added.kind, added.day, added.start, added.end, added.weeks), ("", 4, 3, 4, "8周"))

    def test_conflicting_activity_offers_choices_and_waits_for_confirmation(self):
        with patch("courseflow.assistant.local_today", return_value=date(2026, 10, 19)):
            reply = self.send("周二第一和第二节留作组内评审",
                              {"action": "add_entry", "title": "组内评审", "day": "周二", "periods": [1, 2]})
        self.assertIn("虚构体育", reply["message"])
        self.assertNotIn("result", reply)
        self.assertIn("第 3-4 节", reply["choices"][0]["label"])
        choice = reply["choices"][0]
        with self.assertRaisesRegex(ValueError, "有效的空档"):
            self.workbench.run("assistant_choose", {**choice, "mode": "operate", "index": 99})
        preview = self.workbench.run("assistant_choose", {**choice, "mode": "operate"})["result"]
        self.assertEqual(preview["write_label"], "新增活动")
        self.assertIn("组内评审", preview["rows"][0]["after"])
        self.assertIn("第 3-4 节", preview["rows"][0]["after"])
        self.assertTrue(preview["confirmation"])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_find_time_choices_and_preview_reject_a_changed_source(self):
        with patch("courseflow.assistant.local_today", return_value=date(2026, 10, 19)):
            reply = self.send("第八周找两个小节给设备维护, 让我挑一个",
                              {"action": "add_entry", "title": "设备维护", "week": 8,
                               "find_free": True, "duration_periods": 2})
        self.assertEqual(len(reply["choices"]), 3)
        choice = reply["choices"][0]
        self.assertIn("2026-10-26", choice["label"])
        preview = self.workbench.run("assistant_choose", {**choice, "mode": "operate"})["result"]
        self.assertEqual(self.source.read_bytes(), self.original)
        self.tt.courses.append(Course("其他设备预约", 0, 1, 2, "", "8周"))
        save_source(self.tt, self.source)
        modified = self.source.read_bytes()
        with self.assertRaisesRegex(ValueError, "课表.*已更新"):
            self.workbench.run("assistant_choose", {**choice, "mode": "operate"})
        with self.assertRaisesRegex(ValueError, "课表.*已更新"):
            self.workbench.run("commit", {"token": preview["confirmation"]})
        self.assertEqual(self.source.read_bytes(), modified)

    def test_incomplete_or_nonconsecutive_arrangements_cannot_be_saved(self):
        base = {"action": "add_entry", "title": "摄影社准备"}
        reply = self.send("把摄影社准备加到课表", base)
        self.assertIn("哪天", reply["message"])
        self.assertNotIn("result", reply)
        with self.assertRaisesRegex(ValueError, "需要连续节次"):
            self.send("十月二十日第三和第五节留作摄影社准备",
                      {**base, "date": "2026-10-20", "periods": [3, 5]})
        with self.assertRaisesRegex(ValueError, "无法和课表作息对齐"):
            self.send("十月二十日十一点到十一点半安排摄影社准备",
                      {**base, "date": "2026-10-20", "start_time": "11:00", "end_time": "11:30"})
        chat = self.send("把摄影社准备记到账上", {**base, "message": "请切到课表操作", "date": "2026-10-20", "periods": [7]},
                         mode="chat")
        self.assertNotIn("result", chat)
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_two_images_review_preserves_group_and_selected_duration(self):
        files = []
        for person in ("甲", "乙"):
            path = self.root / f"成员{person}.png"
            Image.new("RGB", (80, 60), "white").save(path)
            files.append({"name": path.name, "path": str(path)})
        course = {"name": "虚构课程", "day": "周二", "periods": "1-2", "weeks": "1-16周", "room": "示例楼"}
        group_intent = {"action": "group", "week": "7", "minutes": "60", "preferred_day": "5"}
        with patch("courseflow.service.ai_settings", return_value=self.config), \
                patch("courseflow.assistant.AIClient.json", side_effect=[group_intent, *([{"courses": [course]}] * 2)]):
            ready = self.workbench.run("assistant", {"mode": "operate",
                                                    "text": "这两张是我和同学的课表, 第七周哪里能凑出一小时, 周五优先",
                                                    "files": files})
        prepared = ready["result"]
        self.assertEqual(prepared["type"], "group_prepare")
        self.assertEqual((prepared["week"], prepared["minutes"], ready["preferred_day"]), (7, 60, 5))
        review = {"token": prepared["token"], "members": [{"name": member["name"]} for member in prepared["members"]],
                  "week": prepared["week"], "minimum": prepared["minimum"], "minutes": prepared["minutes"]}
        reply = self.workbench.run("assistant_choose", {"mode": "operate", "review": review, "preferred_day": ready["preferred_day"]})
        first = reply["slots"][0]
        self.assertEqual(first["day"], 5)
        generation = {"title": "虚构彩排", "room": "", "notes": "", "prep": [],
                      "agenda": [{"title": "彩排演示", "minutes": 40}]}
        with patch("courseflow.service.ai_settings", return_value=self.config), \
                patch("courseflow.assistant.AIClient.json", side_effect=[
                    {"action": "schedule", "number": str(first["number"]), "goal": "安排项目彩排"}, generation]):
            result = self.workbench.run("assistant", {"mode": "operate", "text": "用周五那段排个彩排",
                                                     "group_token": reply["result"]["token"]})["result"]
        draft = result["review"]["draft"]
        self.assertEqual((draft["start"], draft["end"], draft["members"]),
                         (first["time"], first["end"], ["成员甲", "成员乙"]))
        applied = self.workbench.run("schedule", {"operation": "apply", "token": result["token"]})
        preview = self.workbench.run("schedule", {"operation": "preview", "token": applied["token"]})
        self.assertTrue(preview["preview"])
        exported = self.workbench.run("schedule", {"operation": "export", "token": preview["token"]})
        self.assertTrue((self.workbench.exports / exported["files"][0]["id"]).is_file())
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_export_keeps_the_requested_week_and_background(self):
        with patch("courseflow.harness_commands.local_today", return_value=date(2026, 11, 21)):
            reply = self.send("能把下星期的课做成手机锁屏吗, 背景用海边教室, 先看看效果",
                              {"action": "export", "formats": "phone", "week": "13", "background": "海边教室"})
        preview = reply["result"]
        self.assertEqual(preview["formats"], ["phone"])
        self.assertEqual(preview["wallpaper_background"], "海边教室")
        self.assertTrue(preview["wallpaper_previews"]["phone"])
        draft = self.workbench._get_draft(reply["preparation"]["token"], "change")
        self.assertEqual(draft["wallpaper_week"], 12)
        self.assertFalse(self.workbench.exports.exists())
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_assistant_todo_workflow_with_natural_requests(self):
        title = "试用\u00b7整理实验报告"
        added = self.send("11 月 27 日前我得交实验报告, 帮我记到待办里",
                          {"action": "todo", "operation": "add", "title": title, "due": "2026-11-27"})["result"]
        self.assertEqual(added["items"][0]["due"], "2026-11-27")
        listed = self.send("我手头记了哪些任务", {"action": "todo", "operation": "list"})["result"]
        self.assertEqual(listed["items"][0]["title"], title)
        reserved = self.send("帮我腾个空档整理那份报告", {"action": "todo", "operation": "reserve",
                                                   "title": title})["result"]
        self.assertEqual(reserved["type"], "todo_reserve")
        self.assertEqual(reserved["item"]["id"], added["items"][0]["id"])
        for text, operation in (("报告做完了, 帮我勾上", "complete"), ("报告还要改, 放回待办", "reopen")):
            updated = self.send(text, {"action": "todo", "operation": operation, "title": title})["result"]
            self.assertEqual(updated["items"][0]["done"], operation == "complete")
        removed = self.send("删掉刚刚那条试用任务", {"action": "todo", "operation": "remove",
                                                  "title": title})["result"]
        self.assertEqual(removed["items"], [])
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_assistant_todos_share_store_and_resolve_ambiguity(self):
        desktop = todo_list({"operation": "add", "title": "示例报告", "due": "2026-11-27"})["items"][0]
        result = self.send("记一项示例报告", {"action": "todo", "operation": "add", "title": "示例报告"})["result"]
        self.assertEqual(len(result["items"]), 2)
        reply = self.send("完成报告", {"action": "todo", "operation": "complete", "title": "示例报告"})
        self.assertEqual(len(reply["choices"]), 2)
        self.assertTrue(all(not item["done"] for item in todo_list({})["items"]))
        self.workbench.run("assistant_choose", {"mode": "operate", **reply["choices"][0]})
        result = self.workbench.run("request", {"text": "查看待办"})
        self.assertTrue(next(item for item in result["items"] if item["id"] == desktop["id"])["done"])


if __name__ == "__main__":
    unittest.main()
