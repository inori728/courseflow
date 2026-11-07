from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from courseflow import service
from courseflow.agenda import local_today, week_number
from courseflow.cli import main
from courseflow.documents import document_text
from courseflow.drafts import save_notice_draft
from courseflow.group import BusyCard, decode_card
from courseflow.notice import NoticeIntent
from courseflow.parsing import parse_mapped_rows
from courseflow.source import load_source, save_source

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "courseflow" / "data" / "示例课表.yaml"


class WorkflowTests(unittest.TestCase):
    def test_concurrent_file_change_is_not_overwritten_or_backed_up_over_original(self):
        with TemporaryDirectory() as folder:
            target = Path(folder) / "课程.yaml"
            shutil.copyfile(SAMPLE, target)
            original = service.load_timetable(target)
            signature = service.file_signature(target)
            target.write_text("# another writer\n" + target.read_text(encoding="utf-8"), encoding="utf-8")
            updated_text = target.read_bytes()
            with self.assertRaisesRegex(ValueError, "其他程序修改"):
                service.save_timetable(original, target, expected_signature=signature)
            self.assertEqual(target.read_bytes(), updated_text)
            self.assertFalse(target.with_name(target.name + ".bak").exists())

    def test_invalid_import_draft_cannot_destroy_saved_timetable(self):
        with TemporaryDirectory() as folder:
            target = Path(folder) / "课程.yaml"
            bad = Path(folder) / "bad.json"
            shutil.copyfile(SAMPLE, target)
            before = target.read_bytes()
            bad.write_text('{"type":"courseflow-import","version":1,"courses":[]}', encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                result = main(["accept", str(bad), "--confirm", "-o", str(target)])
            self.assertEqual(result, 1)
            self.assertEqual(target.read_bytes(), before)

    def test_cli_notice_preview_and_apply_have_separate_confirmation(self):
        with TemporaryDirectory() as folder:
            target, draft = Path(folder) / "课程.yaml", Path(folder) / "调整.proposal.json"
            shutil.copyfile(SAMPLE, target)
            tt = load_source(target)
            intent = NoticeIntent(course_name="体育", source_week=7, target_week=9, target_day=6, target_periods="7-8")
            save_notice_draft(intent, tt, draft)
            before = target.read_bytes()
            command = ["notice-preview", str(draft), "-f", str(target), "--select", "1"]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(command), 0)
                self.assertEqual(target.read_bytes(), before)
                self.assertEqual(main(command + ["--apply"]), 1)
                self.assertEqual(target.read_bytes(), before)
                self.assertEqual(main(command + ["--apply", "--confirm"]), 0)
            changed = load_source(target)
            sport = next(c for c in changed.courses if "体育" in c.name)
            self.assertEqual((sport.changes[0].week, sport.changes[0].target_week), (7, 9))
            self.assertEqual(target.with_name(target.name + ".bak").read_bytes(), before)

    def test_period_adapter_preserves_course_weeks_and_room(self):
        rows = [["课程名称", "上课星期", "节次", "周次", "教室"], ["数学", "周三", "3-4", "1-16周(单)", "A101"]]
        config = {"format": "records", "header_row": 1, "columns": {
            "name": "课程名称", "day": "上课星期", "periods": "节次", "weeks": "周次", "room": "教室"}}
        courses = parse_mapped_rows(rows, config)
        self.assertEqual((courses[0].name, courses[0].day, courses[0].weeks, courses[0].room), ("数学", 2, "1-16周(单)", "A101"))

    def test_word_table_uses_same_grid_import_and_rejects_broken_zip(self):
        rows = [["节次", "周一", "周二", "周三"], ["1-2", "数学 A101 1-16周", "", ""]]
        xml_rows = "".join("<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{cell}</w:t></w:r></w:p></w:tc>" for cell in row) + "</w:tr>" for row in rows)
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl>' + xml_rows + '</w:tbl></w:body></w:document>'
        with TemporaryDirectory() as folder:
            path = Path(folder) / "课表.docx"
            with ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", xml)
            courses, notes = service.import_document(path)
            self.assertEqual((courses[0].name, courses[0].room), ("数学", "A101"))
            path.write_bytes(b"not a zip")
            with self.assertRaises(ValueError):
                document_text(path)

    def test_midnight_changes_local_day_and_week_at_shanghai_midnight(self):
        tt = load_source(SAMPLE)
        before = local_today(tt, datetime(2026, 10, 18, 15, 59, tzinfo=timezone.utc))
        after = local_today(tt, datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc))
        self.assertEqual(before.isoformat(), "2026-10-18")
        self.assertEqual(after.isoformat(), "2026-10-19")
        self.assertEqual((week_number(tt, before), week_number(tt, after)), (6, 7))

    def test_a4_pdf_has_correct_physical_size_and_single_page(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("Optional PDF dependency not installed")
        with TemporaryDirectory() as folder:
            path = Path(folder) / "挂图.pdf"
            service.export_poster(load_source(SAMPLE), path, 7)
            reader = PdfReader(path)
            self.assertEqual(len(reader.pages), 1)
            box = reader.pages[0].mediabox
            self.assertAlmostEqual(float(box.width), 297 / 25.4 * 72, delta=1)
            self.assertAlmostEqual(float(box.height), 210 / 25.4 * 72, delta=1)
            self.assertEqual(len(reader.pages[0].images), 1)

    def test_packaged_and_hostable_point_pages_are_identical(self):
        self.assertEqual((ROOT / "docs" / "index.html").read_bytes(), service.point_grid_path().read_bytes())

    @unittest.skipUnless(shutil.which("node"), "Node is only needed to verify browser card interoperability")
    def test_busy_card_is_interoperable_with_browser_codec_both_ways(self):
        from datetime import date
        card = BusyCard("测试成员", date(2026, 9, 7), {7: {0, 1, 80, 81}})
        html = service.point_grid_path().read_text(encoding="utf-8")
        codec = re.search(r'<script id="card-codec">([\s\S]*?)</script>', html).group(1)
        script = codec + "\nconst code=" + json.dumps(card.encode()) + ";const decoded=CourseFlowCard.decode(code);console.log(JSON.stringify(decoded));console.log(CourseFlowCard.encode(decoded));"
        result = subprocess.run([shutil.which("node"), "-"], input=script, text=True, encoding="utf-8", capture_output=True, check=True)
        payload, code = result.stdout.strip().splitlines()
        self.assertEqual(json.loads(payload)["name"], card.name)
        self.assertEqual(decode_card(code).busy, card.busy)


if __name__ == "__main__":
    unittest.main()
