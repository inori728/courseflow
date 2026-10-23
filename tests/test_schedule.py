import unittest

from courseflow.model import Change, Course
from courseflow.schedule import period_cells, resolve_blocks, resolve_course


class ScheduleExpansionTests(unittest.TestCase):
    def test_skip_and_change(self):
        course = Course(
            name="高数", day=0, start=1, end=2, room="A101", weeks="1-4周",
            skip=[2],
            changes=[Change(week=3, day=1, start=3, end=4, room="B202")],
        )
        occurrences = resolve_course(course)
        by_week = {occ.week: occ for occ in occurrences}
        self.assertNotIn(2, by_week)
        self.assertEqual((by_week[1].day, by_week[1].room), (0, "A101"))
        self.assertEqual((by_week[3].day, by_week[3].start, by_week[3].end), (1, 3, 4))
        self.assertEqual(by_week[3].room, "B202")
        self.assertEqual((by_week[4].day, by_week[4].room), (0, "A101"))

    def test_unknown_weeks_produce_unknown_occurrence(self):
        course = Course(name="高数", day=0, start=1, end=2, weeks="考试周")
        occurrences = resolve_course(course)
        self.assertEqual(len(occurrences), 1)
        self.assertIsNone(occurrences[0].week)

    def test_blocks_merge_weeks_by_slot(self):
        course = Course(
            name="高数", day=0, start=1, end=2, room="A101", weeks="1-4周",
            skip=[2],
            changes=[Change(week=3, day=1, start=3, end=4, room="B202")],
        )
        blocks = resolve_blocks(course)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].weeks, frozenset({1, 4}))
        self.assertEqual((blocks[1].day, blocks[1].weeks), (1, frozenset({3})))

    def test_period_cells(self):
        course = Course(name="高数", day=0, start=3, end=4, weeks="1周")
        occurrence = resolve_course(course)[0]
        self.assertEqual(period_cells(occurrence), [(0, 3), (0, 4)])


if __name__ == "__main__":
    unittest.main()
