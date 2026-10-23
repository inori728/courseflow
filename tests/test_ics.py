import unittest
from datetime import date, datetime, time, timezone

from courseflow.ics import CalendarError, build_calendar
from courseflow.model import Change, Course, Timetable


def make_timetable(courses):
    return Timetable(
        term="测试学期",
        semester_start=date(2026, 9, 7),
        weeks_total=16,
        period_times={
            1: (time(8, 0), time(8, 45)),
            2: (time(8, 50), time(9, 35)),
            3: (time(10, 0), time(10, 45)),
            4: (time(10, 50), time(11, 35)),
        },
        courses=courses,
    )


FIXED_NOW = datetime(2026, 9, 1, tzinfo=timezone.utc)


class CalendarExportTests(unittest.TestCase):
    def test_odd_weeks_skip_and_change(self):
        tt = make_timetable([
            Course(name="高等数学", day=0, start=1, end=2, room="教一A101",
                   weeks="1-4周(单)", skip=[3]),
            Course(
                name="大学英语", day=0, start=3, end=4, weeks="1-2周",
                changes=[Change(week=2, day=1, start=3, end=4, room="B202")],
            ),
        ])
        text = build_calendar(tt, reminder_minutes=15, now=FIXED_NOW)

        self.assertIn("\r\n", text)
        self.assertEqual(text.count("BEGIN:VEVENT"), 3)
        self.assertIn("DTSTAMP:20260901T000000Z", text)
        self.assertIn("DTSTART:20260907T000000Z", text)
        self.assertIn("DTEND:20260907T013500Z", text)
        self.assertIn("DTSTART:20260915T020000Z", text)
        self.assertIn("DTEND:20260915T033500Z", text)
        self.assertIn("TRIGGER:-PT15M", text)
        self.assertIn("LOCATION:教一A101", text)
        # Week 3 of the odd-week course is skipped.
        self.assertNotIn("20260921T000000Z", text)

    def test_zero_reminder_has_no_alarm(self):
        tt = make_timetable([
            Course(name="高等数学", day=0, start=1, end=2, weeks="1周"),
        ])
        text = build_calendar(tt, reminder_minutes=0, now=FIXED_NOW)
        self.assertNotIn("BEGIN:VALARM", text)

    def test_missing_semester_start_is_rejected(self):
        tt = make_timetable([
            Course(name="高等数学", day=0, start=1, end=2, weeks="1周"),
        ])
        tt.semester_start = None
        with self.assertRaises(CalendarError):
            build_calendar(tt, now=FIXED_NOW)

    def test_unknown_weeks_are_rejected(self):
        tt = make_timetable([
            Course(name="高等数学", day=0, start=1, end=2, weeks="考试周"),
        ])
        with self.assertRaises(CalendarError):
            build_calendar(tt, now=FIXED_NOW)

    def test_missing_period_time_is_rejected(self):
        tt = make_timetable([
            Course(name="高等数学", day=0, start=9, end=10, weeks="1周"),
        ])
        with self.assertRaises(CalendarError):
            build_calendar(tt, now=FIXED_NOW)


if __name__ == "__main__":
    unittest.main()
