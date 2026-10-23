import unittest
from datetime import date, time

from courseflow.model import Timetable
from courseflow.semester import SemesterCalendar, SemesterError


def make_timetable(**overrides):
    values = {
        "term": "测试学期",
        "semester_start": date(2026, 9, 7),
        "weeks_total": 16,
        "period_times": {
            1: (time(8, 0), time(8, 45)),
            2: (time(8, 50), time(9, 35)),
            3: (time(10, 0), time(10, 45)),
            4: (time(10, 50), time(11, 35)),
        },
    }
    values.update(overrides)
    return Timetable(**values)


class SemesterCalendarTests(unittest.TestCase):
    def test_week_and_day_to_date(self):
        calendar = SemesterCalendar.from_timetable(make_timetable())
        self.assertEqual(calendar.date_for(1, 0), date(2026, 9, 7))
        self.assertEqual(calendar.date_for(2, 1), date(2026, 9, 15))

    def test_period_to_time(self):
        calendar = SemesterCalendar.from_timetable(make_timetable())
        start, end = calendar.times_for(1, 2)
        self.assertEqual((start, end), (time(8, 0), time(9, 35)))

    def test_datetime_for_uses_china_offset(self):
        calendar = SemesterCalendar.from_timetable(make_timetable())
        start, end = calendar.datetime_for(1, 0, 1, 2)
        self.assertEqual(start.hour, 8)
        self.assertEqual(end.hour, 9)
        self.assertEqual(start.utcoffset().total_seconds(), 8 * 3600)

    def test_missing_start_is_rejected(self):
        with self.assertRaises(SemesterError):
            SemesterCalendar.from_timetable(make_timetable(semester_start=None))

    def test_non_monday_start_is_rejected(self):
        with self.assertRaises(SemesterError):
            SemesterCalendar.from_timetable(make_timetable(semester_start=date(2026, 9, 8)))

    def test_week_out_of_range_is_rejected(self):
        calendar = SemesterCalendar.from_timetable(make_timetable())
        with self.assertRaises(SemesterError):
            calendar.date_for(17, 0)

    def test_missing_period_time_is_rejected(self):
        calendar = SemesterCalendar.from_timetable(make_timetable())
        with self.assertRaises(SemesterError):
            calendar.times_for(1, 9)


if __name__ == "__main__":
    unittest.main()
