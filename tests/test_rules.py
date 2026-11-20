import json
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from courseflow.model import Course, Timetable
from courseflow.rules import HolidayDataError, _group_spans, holiday_report, import_holiday_data, load_holidays


class HolidayRuleTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        settings = patch("courseflow.rules.settings_dir", return_value=Path(folder.name))
        settings.start()
        self.addCleanup(settings.stop)

    def test_builtin_2026_data(self):
        data = load_holidays(2026)
        self.assertIsNotNone(data)
        self.assertEqual(data.year, 2026)
        self.assertEqual(len(data.days), 39)
        by_date = {day.date: day for day in data.days}
        self.assertTrue(by_date[date(2026, 10, 1)].is_off)
        self.assertFalse(by_date[date(2026, 9, 20)].is_off)
        self.assertFalse(by_date[date(2026, 10, 10)].is_off)

    def test_group_spans_groups_consecutive_days(self):
        data = load_holidays(2026)
        spans = _group_spans(data.days)
        national = [s for s in spans if s.name == "国庆节" and s.is_off]
        self.assertEqual(len(national), 1)
        self.assertEqual(national[0].start, date(2026, 10, 1))
        self.assertEqual(national[0].end, date(2026, 10, 7))

    def test_report_lists_off_day_courses_and_workdays(self):
        tt = Timetable(
            semester_start=date(2026, 9, 7),
            weeks_total=16,
            courses=[
                Course(name="高等数学", day=3, start=1, end=2, weeks="1-16周", room="A101"),
            ],
        )
        report = holiday_report(tt)
        self.assertEqual(report.warnings, [])
        national = [
            n for n in report.notices
            if n.name == "国庆节" and n.is_off and n.start == date(2026, 10, 1)
        ]
        self.assertEqual(len(national), 1)
        self.assertEqual(national[0].end, date(2026, 10, 7))
        self.assertTrue(any("高等数学" in item for item in national[0].affected))
        workdays = [n for n in report.notices if not n.is_off and n.name == "国庆节"]
        self.assertEqual(len(workdays), 2)
        self.assertEqual(tt.courses[0].skip, [])
        self.assertEqual(tt.courses[0].changes, [])

    def test_missing_semester_start_is_reported(self):
        tt = Timetable(courses=[Course(name="高等数学", day=0, start=1, end=2, weeks="1周")])
        report = holiday_report(tt)
        self.assertTrue(any("semester_start" in item for item in report.warnings))

    def test_missing_year_data_is_reported(self):
        tt = Timetable(
            semester_start=date(2030, 9, 2),
            weeks_total=16,
            courses=[],
        )
        report = holiday_report(tt)
        self.assertTrue(any("2030" in item for item in report.warnings))

    def test_import_future_year_preserves_previous_data_on_invalid_replacement(self):
        with TemporaryDirectory() as folder, patch("courseflow.rules.settings_dir", return_value=Path(folder)):
            source = Path(folder) / "fixture.json"
            item = {"name": "虚构假期", "date": "2030-09-02", "isOffDay": True}
            source.write_text(json.dumps({"year": 2030, "days": [item]}), encoding="utf-8")
            target = import_holiday_data(source, 2030)
            self.assertEqual(load_holidays(2030).days[0].name, "虚构假期")
            before = target.read_bytes()
            source.write_text(json.dumps({"year": 2030, "days": [item, item]}), encoding="utf-8")
            with self.assertRaises(HolidayDataError):
                import_holiday_data(source)
            self.assertEqual(target.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
