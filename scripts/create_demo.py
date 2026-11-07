"""Render a README animation using the fictional bundled sample."""
from __future__ import annotations

import copy
from pathlib import Path
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from courseflow import service
from courseflow.model import Change
from courseflow.render import load_font


def main():
    timetable = service.load_timetable(ROOT / "courseflow" / "data" / "示例课表.yaml")
    timetable = copy.deepcopy(timetable)
    sport = next(course for course in timetable.courses if "体育" in course.name)
    sport.changes.append(Change(week=7, target_week=9, day=6, start=7, end=8))
    frames = []
    for week, caption in [(7, "第 7 周: 体育已移走"), (8, "第 8 周: 游泳课停课"), (9, "第 9 周: 保留原体育课, 周日增加补课")]:
        schedule = service.preview_wallpaper(timetable, size=(1320, 860), week=week, theme="paper", text_mode="auto")
        frame = Image.new("RGB", (1320, 940), "#eef2ff")
        frame.paste(schedule, (0, 0))
        draw = ImageDraw.Draw(frame)
        draw.text((45, 884), caption + " / 虚构数据演示", fill="#344667", font=load_font(26, True))
        frame.thumbnail((1000, 720), Image.Resampling.LANCZOS)
        frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=128))
    target = ROOT / "docs" / "assets" / "preview.gif"
    target.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(target, save_all=True, append_images=frames[1:], duration=2200, loop=0, optimize=True, disposal=2)
    print(target.relative_to(ROOT))


if __name__ == "__main__":
    main()
