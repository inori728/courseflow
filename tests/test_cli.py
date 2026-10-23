import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from courseflow.cli import main


class CliTests(unittest.TestCase):
    def test_calendar_command_exports_file(self):
        sample = Path(__file__).resolve().parents[1] / "courseflow" / "data" / "示例课表.yaml"
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "课表.ics"
            rc = main(["calendar", "-f", str(sample), "-o", str(out), "--remind", "0"])
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            text = out.read_text(encoding="utf-8")
            self.assertIn("BEGIN:VCALENDAR", text)
            self.assertIn("BEGIN:VEVENT", text)

    def test_calendar_without_semester_start_returns_error(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "old.yaml"
            src.write_text(
                "term: 旧课表\ncourses:\n- name: 高数\n  day: 周一\n"
                "  periods: 1-2\n  weeks: 1周\n  room: A101\n",
                encoding="utf-8",
            )
            out = Path(tmp) / "课表.ics"
            rc = main(["calendar", "-f", str(src), "-o", str(out)])
            self.assertEqual(rc, 1)
            self.assertFalse(out.exists())

    def test_check_strict_returns_one_on_conflict(self):
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "conflict.yaml"
            src.write_text(
                "term: 冲突\ncourses:\n"
                "- name: A\n  day: 周一\n  periods: 1-2\n  weeks: 1周\n  room: A101\n"
                "- name: B\n  day: 周一\n  periods: 2-3\n  weeks: 1周\n  room: B202\n",
                encoding="utf-8",
            )
            self.assertEqual(main(["check", "-f", str(src)]), 0)
            self.assertEqual(main(["check", "-f", str(src), "--strict"]), 1)


if __name__ == "__main__":
    unittest.main()
