"""GUI executable entry point; no API request or data write at startup."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def self_check(source, target):
    application = None
    report = {}
    try:
        import ctypes
        import decimal
        import io
        import ssl
        from openpyxl import Workbook, load_workbook
        from pypdf import PdfReader
        from courseflow import __version__, service
        from courseflow.gui.app import CourseFlowApp
        del ctypes, PdfReader
        ssl.create_default_context()
        assert decimal.Decimal("1.25") * 2 == decimal.Decimal("2.50")
        workbook = Workbook()
        workbook.active["A1"] = "CourseFlow"
        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)
        assert load_workbook(buffer).active["A1"].value == "CourseFlow"
        sample = Path(service.__file__).resolve().parent / "data" / "示例课表.yaml"
        timetable = service.load_timetable(sample)
        application = CourseFlowApp(source)
        application.withdraw()
        for page in ("import", "review", "export", "group"):
            application.go(page)
            application.update_idletasks()
        application.go("review")
        application.calendar_view.set_week(7)
        application.update_idletasks()
        assert application.calendar_view.canvas.find_withtag("course")
        image = service.preview_wallpaper(timetable, size=(1280, 800), week=7, theme="paper")
        card = service.make_busy_card(timetable, "Smoke test", [7])
        group = service.group_free([card], 7)
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temporary:
            shared = service.export_point_grid(Path(temporary) / "share.html", timetable, week=7)
            assert '"week":7' in shared.read_text(encoding="utf-8")
        report = {
            "version": __version__, "courses": len(timetable),
            "point_grid": service.point_grid_path().is_file(),
            "point_grid_export": True,
            "in_app_week_calendar": True,
            "window": application.winfo_exists() == 1,
            "pages": ["import", "review", "export", "group"],
            "ctypes_ssl_decimal": True, "excel_roundtrip": True,
            "pdf_import_available": True, "render_size": image.size,
            "group_windows": len(group.windows), "status": "passed",
        }
    except Exception as exc:
        report = {"status": "failed", "error_type": type(exc).__name__, "message": str(exc)}
    finally:
        if application is not None:
            application.destroy()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report.get("status") == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description="CourseFlow 桌面课表工具")
    parser.add_argument("--file", help="启动时打开的课表源文件")
    parser.add_argument("--self-check", metavar="JSON", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.self_check:
        return self_check(args.file, Path(args.self_check))
    else:
        from courseflow.gui import main as run_gui
        run_gui(args.file)


if __name__ == "__main__":
    raise SystemExit(main())
