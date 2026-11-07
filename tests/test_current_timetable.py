from datetime import date
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from courseflow import service
from courseflow.model import Course, Timetable
from courseflow.notice import NoticeIntent


def timetable():
    return Timetable(semester_start=date(2026, 9, 7), weeks_total=16,
                     courses=[Course("体育", 1, 7, 8, "操场", "1-16周")])


class CurrentTimetableTests(unittest.TestCase):
    def test_week_view_removes_original_occurrence_and_shows_target_week(self):
        tt = timetable()
        intent = NoticeIntent(course_name="体育", source_week=9, target_week=14,
                              target_day=5, target_periods="7-8")
        preview = service.notice_preview(tt, intent, service.notice_candidates(tt, intent))
        changed = service.apply_notification(tt, preview)
        self.assertEqual(preview.focus_week, 14)
        self.assertEqual(preview.focus_period, 7)
        self.assertEqual(service.week_calendar_data(changed, 9)["courses"], [])
        target = service.week_calendar_data(changed, 14)
        self.assertEqual([(item.day, item.source_week) for item in target["courses"]], [(1, 14), (5, 9)])
        self.assertEqual(target["dates"][5].isoformat(), "2026-12-12")
        self.assertEqual(len(service.week_calendar_data(tt, 9)["courses"]), 1)

    def test_cancel_focuses_original_week_and_unknown_weeks_are_not_confirmed_classes(self):
        tt = timetable()
        intent = NoticeIntent(course_name="体育", source_week=9, action="cancel")
        preview = service.notice_preview(tt, intent, service.notice_candidates(tt, intent))
        self.assertEqual(preview.focus_week, 9)
        unknown = Timetable(courses=[Course("待核对课程", 0, 1, 2)])
        view = service.week_calendar_data(unknown, 1)
        self.assertEqual(view["courses"], [])
        self.assertEqual(view["unknown"], ["待核对课程"])
        self.assertTrue(view["date_note"])

    def test_saved_current_source_is_remembered_and_readable_after_reopen(self):
        with TemporaryDirectory() as folder, patch.dict(os.environ, {"COURSEFLOW_HOME": folder}):
            path = Path(folder) / "current.yaml"
            service.save_timetable(timetable(), path, expected_signature="")
            self.assertTrue(service.remember_current_source(path))
            self.assertEqual(service.default_gui_source().resolve(), path.resolve())
            self.assertEqual(service.load_timetable(service.default_gui_source()).courses[0].name, "体育")

    def test_broken_recent_source_settings_fall_back_to_the_stored_timetable(self):
        with TemporaryDirectory() as folder, patch.dict(os.environ, {"COURSEFLOW_HOME": folder}):
            path = Path(folder) / "课表.yaml"
            service.save_timetable(timetable(), path)
            (Path(folder) / "session.json").write_text("broken JSON", encoding="utf-8")
            self.assertEqual(service.default_gui_source().resolve(), path.resolve())


if __name__ == "__main__":
    unittest.main()
