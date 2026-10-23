"""term 命令行入口--迭代 3 的六条命令:

    term demo             第一次用先跑这个:示例课表 + 一张壁纸
    term import 文件      从 Excel(.xlsx) / CSV 导入课表
    term paste            把剪贴板里的课表文字导进来
    term wallpaper        从课表源文件出壁纸(默认电脑版 + 手机版)
    term check            给课表做一次校对:时间冲突 / 待完善 / 改动明细
    term calendar         导出 .ics 日历(单双周 / 停课 / 调课生效)

(也可以在仓库目录里用  python -m courseflow  跑同样的命令.)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from . import service
from .backgrounds import BACKGROUNDS, normalize as normalize_bg
from .source import SourceFileError

DEFAULT_SOURCE = Path("课表.yaml")
SAMPLE_PATH = Path(__file__).resolve().parent / "data" / "示例课表.yaml"


def _print_courses(courses, limit: int = 8) -> None:
    print(f"  解析出 {len(courses)} 条课程安排:")
    for c in courses[:limit]:
        extra = f" @{c.room}" if c.room else ""
        weeks = f"({c.weeks})" if c.weeks else ""
        print(f"   · {c.slot_text()} {c.name}{extra}{weeks}")
    if len(courses) > limit:
        print(f"   · ...等共 {len(courses)} 条")


def _print_review(courses, notes=None) -> None:
    """导入之后的校对小结(想全部展开就单独跑  term check)."""
    rev = service.review_courses(courses)
    items = rev.conflicts + rev.issues
    if items:
        print(f"· 校对:发现 {len(items)} 处待确认")
        for x in items[:3]:
            print(f"   - {x}")
        if len(items) > 3:
            print(f"   - (还有 {len(items) - 3} 处,跑 term check 看全部)")
    else:
        print("· 校对:没发现明显问题")
    notes = notes or []
    for x in notes[:3]:
        print(f"   ! {x}")
    if len(notes) > 3:
        print(f"   ! (还有 {len(notes) - 3} 个格子无法识别)")


def _open_folder(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", str(path)])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def _run_wallpaper(source: Path, args) -> int:
    tt = service.load_timetable(source)
    for w in tt.warnings:
        print(f"   ! {w}")
    print(f"· 读课表:{source}(共 {len(tt)} 条)")

    results = service.render_wallpapers(
        tt, out_dir=args.out, which=args.size, background=normalize_bg(args.bg),
    )
    for path, size in results:
        print(f"· 出图:{path.name}({size[0]}×{size[1]})")
    out_dir = results[0][0].parent
    print(f"√ 完成!壁纸在:{out_dir}")
    if not args.no_open:
        _open_folder(out_dir)
    return 0


def cmd_demo(args) -> int:
    print("= CourseFlow 快速演示 =")
    target = DEFAULT_SOURCE
    if service.prepare_demo_source(target, SAMPLE_PATH, force=args.force):
        print(f"· 已生成示例课表:{target}(用记事本打开就能改)")
    else:
        print(f"· 已经存在 {target}(想重置成示例课表就加 --force)")
    return _run_wallpaper(target, args)


def cmd_wallpaper(args) -> int:
    return _run_wallpaper(Path(args.file or DEFAULT_SOURCE), args)


def _import_common(courses, out_arg) -> int:
    target = Path(out_arg or DEFAULT_SOURCE)
    tt = service.prepare_import(courses, target)
    backup = service.save_timetable(tt, target)
    if backup is not None:
        print(f"   原文件已备份为:{backup.name}")
    print(f"   已写入:{target}")
    print("· 下一步:term wallpaper 出一张看看;想改课表就直接改这个文件,改完可跑 term check 复查")
    if tt.semester_start is None or not tt.period_times:
        print("  想导日历:先在源文件补 semester_start / period_times,再跑 term calendar")
    return 0


def cmd_import(args) -> int:
    print("= 从文件导入课表 =")
    courses, notes = service.import_table(args.path)
    _print_courses(courses)
    _print_review(courses, notes)
    return _import_common(courses, args.out)


def cmd_paste(args) -> int:
    print("= 从剪贴板导入课表 =")
    courses, notes = service.import_clipboard()
    _print_courses(courses)
    _print_review(courses, notes)
    return _import_common(courses, args.out)


def cmd_check(args) -> int:
    print("= 课表校对 =")
    source = Path(args.file or DEFAULT_SOURCE)
    tt = service.load_timetable(source)
    for w in tt.warnings:
        print(f"   ! {w}")
    print(f"· 读课表:{source}(共 {len(tt)} 条)")
    rev = service.review_timetable(tt)
    print(f"· 时间冲突:{len(rev.conflicts)} 处")
    for x in rev.conflicts:
        print(f"   - {x}")
    print(f"· 待完善:{len(rev.issues)} 处")
    for x in rev.issues:
        print(f"   - {x}")
    print(f"· 改动明细:{len(rev.changes)} 处")
    for x in rev.changes:
        print(f"   - {x}")
    if rev.problem_count == 0:
        print("√ 检查完:没发现明显问题")
    else:
        print("√ 检查完:上面这些请人工确认;改完课表再跑一遍本命令")
    if args.strict and rev.problem_count:
        return 1
    return 0


def cmd_calendar(args) -> int:
    print("= 导出日历 =")
    source = Path(args.file or DEFAULT_SOURCE)
    tt = service.load_timetable(source)
    for w in tt.warnings:
        print(f"   ! {w}")
    print(f"· 读课表:{source}(共 {len(tt)} 条)")
    path = service.export_calendar(
        tt, out=args.out, reminder_minutes=args.remind,
    )
    print(f"√ 完成!日历文件在:{path}")
    return 0


def _add_render_flags(sp: argparse.ArgumentParser, with_file: bool = True) -> None:
    if with_file:
        sp.add_argument("-f", "--file", help="课表源文件(默认 课表.yaml)")
    sp.add_argument("--size", choices=["both", "desktop", "phone"], default="both",
                    help="出图尺寸:both=电脑+手机(默认),desktop,phone")
    sp.add_argument("--bg", default="dusk",
                    help="内置背景:dusk 黄昏晚霞(默认)/ night 深夜星河 / sea 海盐渐变 / purple 暮紫渐变")
    sp.add_argument("-o", "--out", help="输出文件夹(默认:桌面\\课表壁纸)")
    sp.add_argument("--no-open", action="store_true", help="出图后不自动打开文件夹")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="term",
        description="CourseFlow 课表工具:把课表变成壁纸(本地运行,不需要联网)",
    )
    p.add_argument("--version", action="version", version=f"CourseFlow {__version__}")
    sub = p.add_subparsers(dest="cmd", metavar="命令")

    sp = sub.add_parser("demo", help="第一次用先跑这个:生成示例课表 + 出一张壁纸")
    sp.add_argument("--force", action="store_true", help="已有 课表.yaml 时也重置成示例")
    _add_render_flags(sp, with_file=False)

    sp = sub.add_parser("wallpaper", help="从课表源文件出壁纸")
    _add_render_flags(sp)

    sp = sub.add_parser("import", help="从 Excel(.xlsx) / CSV 导入课表")
    sp.add_argument("path", help="要导入的文件路径")
    sp.add_argument("-o", "--out", help="写入的课表源文件(默认 课表.yaml,旧文件自动备份 .bak)")

    sp = sub.add_parser("paste", help="把剪贴板里的课表文字导进来")
    sp.add_argument("-o", "--out", help="写入的课表源文件(默认 课表.yaml,旧文件自动备份 .bak)")

    sp = sub.add_parser("check", help="给课表做一次校对:时间冲突 / 待完善 / 改动明细")
    sp.add_argument("-f", "--file", help="课表源文件(默认 课表.yaml)")
    sp.add_argument("--strict", action="store_true",
                    help="有冲突或待完善时返回非 0(默认仍返回 0)")

    sp = sub.add_parser("calendar", help="导出 .ics 日历(手机/电脑日历可导入)")
    sp.add_argument("-f", "--file", help="课表源文件(默认 课表.yaml)")
    sp.add_argument("-o", "--out", help="输出 .ics 文件(默认 桌面\\课表.ics)")
    sp.add_argument("--remind", type=int, default=15,
                    help="课前提醒分钟数,0=不提醒(默认 15)")

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help()
        print("\n提示:第一次用先跑  term demo")
        return 0

    # 背景名核对(给出可选项,别让用户猜)
    if getattr(args, "bg", None) is not None:
        key = normalize_bg(args.bg)
        if key not in BACKGROUNDS:
            options = ",".join(f"{k}({v})" for k, v in BACKGROUNDS.items())
            print(f"× 无法识别的背景:{args.bg}\n  可选:{options}")
            return 1
        args.bg = key

    try:
        if args.cmd == "demo":
            return cmd_demo(args)
        if args.cmd == "wallpaper":
            return cmd_wallpaper(args)
        if args.cmd == "import":
            return cmd_import(args)
        if args.cmd == "paste":
            return cmd_paste(args)
        if args.cmd == "check":
            return cmd_check(args)
        if args.cmd == "calendar":
            return cmd_calendar(args)
    except (SourceFileError, ValueError) as exc:
        print(f"\n× 出错了:{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
