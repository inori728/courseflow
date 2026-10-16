"""term 命令行入口--迭代 1 的四条命令:

    term demo             第一次用先跑这个:示例课表 + 一张壁纸
    term import 文件      从 Excel(.xlsx) / CSV 导入课表
    term paste            把剪贴板里的课表文字导进来
    term wallpaper        从课表源文件出壁纸(默认电脑版 + 手机版)

(也可以在仓库目录里用  python -m courseflow  跑同样的命令.)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .backgrounds import BACKGROUNDS, normalize as normalize_bg
from .model import SourceFileError, Timetable, load_source, save_source
from .parsing import parse_pasted_text, parse_table_file, read_clipboard_text
from .render import default_wallpaper_dir, render_to_files

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


def _write_source(tt: Timetable, target: Path) -> None:
    if target.exists():
        backup = target.with_name(target.name + ".bak")
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"   原文件已备份为:{backup.name}")
    save_source(tt, target)
    print(f"   已写入:{target}")


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
    tt = load_source(source)
    for w in tt.warnings:
        print(f"   ! {w}")
    print(f"· 读课表:{source}(共 {len(tt)} 条)")

    results = render_to_files(
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
    if target.exists() and not args.force:
        print(f"· 已经存在 {target}(想重置成示例课表就加 --force)")
    else:
        target.write_text(SAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"· 已生成示例课表:{target}(用记事本打开就能改)")
    return _run_wallpaper(target, args)


def cmd_wallpaper(args) -> int:
    return _run_wallpaper(Path(args.file or DEFAULT_SOURCE), args)


def _import_common(courses, out_arg) -> int:
    target = Path(out_arg or DEFAULT_SOURCE)
    tt = Timetable(courses=courses)
    if target.exists():
        try:  # 沿用旧文件里的学期名
            tt.term = load_source(target).term
        except Exception:
            pass
    _write_source(tt, target)
    print("· 下一步:term wallpaper 出一张看看;想改课表直接编辑这个文件")
    return 0


def cmd_import(args) -> int:
    print("= 从文件导入课表 =")
    courses = parse_table_file(args.path)
    _print_courses(courses)
    return _import_common(courses, args.out)


def cmd_paste(args) -> int:
    print("= 从剪贴板导入课表 =")
    text = read_clipboard_text()
    courses = parse_pasted_text(text)
    _print_courses(courses)
    return _import_common(courses, args.out)


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
            print(f"× 不认识的背景:{args.bg}\n  可选:{options}")
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
    except (SourceFileError, ValueError) as exc:
        print(f"\n× 出错了:{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
