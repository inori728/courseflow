import unittest
from datetime import date, time
from pathlib import Path
from tempfile import TemporaryDirectory

from courseflow import service
from courseflow.model import Change, Course


class ServiceTests(unittest.TestCase):
    def test_import_example_xlsx(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "示例课表.xlsx"
        courses, notes = service.import_table(path)
        self.assertEqual(len(courses), 17)
        self.assertEqual(notes, [])

    def test_prepare_import_preserves_term_and_backs_up(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "课表.yaml"
            target.write_text(
                "term: 旧学期\ncourses:\n- name: 旧课\n  day: 周一\n"
                "  periods: 1-2\n  weeks: 1周\n  room: A101\n",
                encoding="utf-8",
            )
            tt = service.prepare_import(
                [Course(name="新课", day=1, start=3, end=4, weeks="2周")],
                target,
            )
            self.assertEqual(tt.term, "旧学期")

            backup = service.save_timetable(tt, target)
            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())
            self.assertIn("新课", target.read_text(encoding="utf-8"))

    def test_prepare_import_keeps_annotations_for_same_slot(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "课表.yaml"
            target.write_text(
                "term: 旧学期\n"
                "semester_start: 2026-09-07\n"
                "weeks_total: 18\n"
                "timezone: Asia/Shanghai\n"
                "period_times:\n  1: 08:00-08:45\n  2: 08:50-09:35\n"
                "courses:\n"
                "- name: 高数\n  day: 周一\n  periods: 1-2\n  weeks: 1-16周\n"
                "  room: A101\n  skip: [3]\n"
                "  changes:\n  - week: 5\n    room: B202\n",
                encoding="utf-8",
            )
            new_course = Course(name="高数", day=0, start=1, end=2, weeks="1-16周", room="A101")
            tt = service.prepare_import([new_course], target)

            self.assertEqual(tt.term, "旧学期")
            self.assertEqual(tt.semester_start, date(2026, 9, 7))
            self.assertEqual(tt.weeks_total, 18)
            self.assertIn(1, tt.period_times)
            self.assertEqual(new_course.skip, [3])
            self.assertEqual(len(new_course.changes), 1)
            self.assertEqual(new_course.changes[0].week, 5)
            self.assertEqual(new_course.changes[0].room, "B202")

    def test_prepare_import_warns_when_annotation_is_dropped(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "课表.yaml"
            target.write_text(
                "term: 旧学期\ncourses:\n- name: 高数\n  day: 周一\n"
                "  periods: 1-2\n  weeks: 1-16周\n  room: A101\n  skip: [3]\n",
                encoding="utf-8",
            )
            tt = service.prepare_import(
                [Course(name="高数", day=1, start=3, end=4, weeks="1-16周")],
                target,
            )
            self.assertTrue(any("未保留" in item for item in tt.warnings))


if __name__ == "__main__":
    unittest.main()
