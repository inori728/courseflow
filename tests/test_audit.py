import unittest

from courseflow.audit import review
from courseflow.model import Change, Course, Timetable


class AuditTests(unittest.TestCase):
    def test_week_overlap_is_reported(self):
        tt = Timetable(courses=[
            Course(name="A", day=0, start=1, end=2, weeks="1-4周"),
            Course(name="B", day=0, start=2, end=3, weeks="2-5周"),
        ])
        conflicts = review(tt).conflicts
        self.assertEqual(len(conflicts), 1)
        self.assertIn("第 2-4 周", conflicts[0])

    def test_two_week_overlap_uses_range(self):
        tt = Timetable(courses=[
            Course(name="A", day=0, start=1, end=2, weeks="1-3周"),
            Course(name="B", day=0, start=2, end=3, weeks="2-4周"),
        ])
        conflicts = review(tt).conflicts
        self.assertEqual(len(conflicts), 1)
        self.assertIn("第 2-3 周", conflicts[0])

    def test_slot_text_has_space_before_period_marker(self):
        course = Course(name="A", day=0, start=1, end=2)
        self.assertEqual(course.slot_text(), "周一 1-2 节")

    def test_skip_removes_conflict(self):
        tt = Timetable(courses=[
            Course(name="A", day=0, start=1, end=2, weeks="1-4周", skip=[2]),
            Course(name="B", day=0, start=1, end=2, weeks="2周"),
        ])
        self.assertEqual(review(tt).conflicts, [])

    def test_change_adds_conflict(self):
        tt = Timetable(courses=[
            Course(
                name="A", day=0, start=1, end=2, weeks="1-4周",
                changes=[Change(week=3, day=1, start=3, end=4)],
            ),
            Course(name="B", day=1, start=3, end=4, weeks="3周"),
        ])
        conflicts = review(tt).conflicts
        self.assertEqual(len(conflicts), 1)
        self.assertIn("第 3 周", conflicts[0])

    def test_unknown_weeks_are_reported_as_unknown(self):
        tt = Timetable(courses=[
            Course(name="A", day=0, start=1, end=2, weeks="考试周"),
            Course(name="B", day=0, start=1, end=2, weeks="1周"),
        ])
        result = review(tt)
        self.assertEqual(len(result.conflicts), 1)
        self.assertIn("周次无法确认", result.conflicts[0])
        self.assertTrue(any("周次无法识别" in item for item in result.issues))

    def test_disjoint_weeks_do_not_conflict(self):
        tt = Timetable(courses=[
            Course(name="A", day=0, start=1, end=2, weeks="1-4周"),
            Course(name="B", day=0, start=1, end=2, weeks="5-8周"),
        ])
        self.assertEqual(review(tt).conflicts, [])


if __name__ == "__main__":
    unittest.main()
