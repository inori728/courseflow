from datetime import date, time
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from courseflow.group import BusyCard, GroupError, card_from_timetable, common_free, decode_card, export_meeting
from courseflow.model import Change, Course, Timetable


class GroupAvailabilityTests(unittest.TestCase):
    def test_card_roundtrip_contains_no_course_names_or_rooms(self):
        tt = Timetable(semester_start=date(2026, 9, 7), courses=[Course("个人课程名称", 0, 1, 2, "个人教室", "1-16周")])
        card = card_from_timetable(tt, "甲")
        public = json.dumps(card.payload(), ensure_ascii=False)
        self.assertNotIn("个人课程名称", public)
        self.assertNotIn("个人教室", public)
        self.assertEqual(decode_card(card.encode()).busy, card.busy)

    def test_incomplete_or_tampered_card_is_rejected(self):
        code = BusyCard("甲", date(2026, 9, 7), {7: {0, 1}}).encode()
        with self.assertRaises(GroupError):
            decode_card(code[:-1] + ("1" if code[-1] != "1" else "2"))

    def test_unknown_week_is_not_assumed_free(self):
        cards = [BusyCard("甲", date(2026, 9, 7), {7: set()}), BusyCard("乙", date(2026, 9, 7), {8: set()})]
        with self.assertRaisesRegex(GroupError, "没有提供"):
            common_free(cards, 7)

    def test_different_semester_anchors_align_to_real_dates(self):
        first = BusyCard("甲", date(2026, 9, 7), {2: {0, 1}})
        second = BusyCard("乙", date(2026, 9, 14), {1: {2, 3}})
        result = common_free([first, second], 2)
        self.assertEqual(result.monday, date(2026, 9, 14))
        monday = [window for window in result.windows if window.day == 0]
        self.assertEqual([(w.start, w.end) for w in monday], [(5, 12)])

    def test_odd_weeks_skips_and_cross_week_moves_are_reflected(self):
        tt = Timetable(semester_start=date(2026, 9, 7), courses=[
            Course("课", 0, 1, 2, weeks="1-16周(单)", skip=[3],
                   changes=[Change(week=7, target_week=8, day=2, start=5, end=6)]),
        ])
        card = card_from_timetable(tt, "甲")
        self.assertEqual(card.busy[2], set())
        self.assertEqual(card.busy[3], set())
        self.assertEqual(card.busy[7], set())
        self.assertEqual(card.busy[8], {28, 29})

    def test_different_period_times_require_explicit_resolution(self):
        cards = [BusyCard("甲", date(2026, 9, 7), {1: set()}, {1: (time(8), time(8, 45))}),
                 BusyCard("乙", date(2026, 9, 7), {1: set()}, {1: (time(9), time(9, 45))})]
        with self.assertRaisesRegex(GroupError, "作息不同"):
            common_free(cards, 1)

    def test_unknown_course_weeks_are_not_omitted_from_busy_data(self):
        tt = Timetable(semester_start=date(2026, 9, 7), courses=[Course("课", 0, 1, 2, weeks="考试周")])
        with self.assertRaisesRegex(GroupError, "周次无法确认"):
            card_from_timetable(tt, "甲")

    def test_meeting_subset_uses_real_date_and_rejects_zero_period(self):
        card = BusyCard("甲", date(2026, 9, 7), {7: set()},
                        {3: (time(10), time(10, 45)), 4: (time(10, 50), time(11, 35))})
        result = common_free([card], 7)
        sunday = next(window for window in result.windows if window.day == 6)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "meeting.ics"
            for first, last in [(0, 4), (3, 0)]:
                with self.assertRaises(GroupError):
                    export_meeting(result, sunday, "讨论", path, first, last)
                self.assertFalse(path.exists())
            export_meeting(result, sunday, "讨论", path, 3, 4)
            content = path.read_text(encoding="utf-8")
            self.assertIn("DTSTART:20261025T020000Z", content)
            self.assertIn("DTEND:20261025T033500Z", content)


if __name__ == "__main__":
    unittest.main()
