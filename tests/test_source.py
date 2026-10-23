import unittest
from datetime import date, time
from pathlib import Path
from tempfile import TemporaryDirectory

from courseflow.source import SourceFileError, load_source, save_source


YAML_TEXT = """\
term: 测试学期
schema_version: 2
custom_top: keep
courses:
- name: 高数
  day: 周一
  periods: 1-2
  weeks: 1-16周(单)
  room: A101
  note: keep
  skip: [3]
  changes:
  - week: 10
    day: 周二
    periods: 3-4
    room: B202
    note: keep-change
  - week: 10
    room: C303
"""


class SourceFileTests(unittest.TestCase):
    def test_load_save_keeps_unknown_fields_and_dedupes_changes(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "课表.yaml"
            src.write_text(YAML_TEXT, encoding="utf-8")
            tt = load_source(src)

            self.assertEqual(tt.schema_version, 2)
            self.assertEqual(tt.extra["custom_top"], "keep")
            self.assertTrue(any("custom_top" in item for item in tt.warnings))
            self.assertTrue(any("重复" in item for item in tt.warnings))

            course = tt.courses[0]
            self.assertEqual(course.extra["note"], "keep")
            self.assertEqual(len(course.changes), 1)
            self.assertEqual(course.changes[0].extra["note"], "keep-change")

            out = Path(tmp) / "out.yaml"
            save_source(tt, out)
            again = load_source(out)
            self.assertEqual(again.schema_version, 2)
            self.assertEqual(again.extra["custom_top"], "keep")
            self.assertEqual(again.courses[0].extra["note"], "keep")
            self.assertEqual(again.courses[0].changes[0].extra["note"], "keep-change")

    def test_empty_skip_has_no_warning(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "课表.yaml"
            src.write_text(
                "term: 测试\ncourses:\n- name: 高数\n  day: 周一\n"
                "  periods: 1-2\n  weeks: 1-16周\n  room: A101\n  skip: []\n",
                encoding="utf-8",
            )
            tt = load_source(src)
            self.assertEqual(tt.warnings, [])

    def test_invalid_change_periods_are_skipped(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "课表.yaml"
            src.write_text(
                "term: 测试\ncourses:\n- name: 高数\n  day: 周一\n"
                "  periods: 1-2\n  weeks: 1-16周\n  room: A101\n"
                "  changes:\n  - week: 10\n    periods: 20-22\n",
                encoding="utf-8",
            )
            tt = load_source(src)
            self.assertEqual(tt.courses[0].changes, [])
            self.assertTrue(any("1-12" in item for item in tt.warnings))

    def test_missing_file_raises_source_error(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(SourceFileError):
                load_source(Path(tmp) / "missing.yaml")

    def test_semester_fields_roundtrip(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "课表.yaml"
            src.write_text(
                "term: 测试\n"
                "semester_start: 2026-09-07\n"
                "weeks_total: 18\n"
                "timezone: Asia/Shanghai\n"
                "period_times:\n  1: 08:00-08:45\n  2: 08:50-09:35\n"
                "courses:\n- name: 高数\n  day: 周一\n  periods: 1-2\n"
                "  weeks: 1-18周\n  room: A101\n",
                encoding="utf-8",
            )
            tt = load_source(src)
            self.assertEqual(tt.semester_start, date(2026, 9, 7))
            self.assertEqual(tt.weeks_total, 18)
            self.assertEqual(tt.period_times[1], (time(8, 0), time(8, 45)))

            out = Path(tmp) / "out.yaml"
            save_source(tt, out)
            again = load_source(out)
            self.assertEqual(again.semester_start, date(2026, 9, 7))
            self.assertEqual(again.weeks_total, 18)
            self.assertEqual(again.period_times[2], (time(8, 50), time(9, 35)))


if __name__ == "__main__":
    unittest.main()
