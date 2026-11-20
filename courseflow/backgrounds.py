"""Bundled wallpaper artwork and backwards-compatible preset names."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps


BACKGROUNDS = {
    "dusk": "樱花电车",
    "night": "月夜海岸",
    "sea": "海边教室",
    "purple": "山间静湖",
}
_ALIASES = {
    **{label: key for key, label in BACKGROUNDS.items()},
    "黄昏晚霞": "dusk", "晚霞": "dusk",
    "深夜星河": "night", "星河": "night",
    "海盐渐变": "sea", "海盐": "sea",
    "暮紫渐变": "purple", "暮紫": "purple",
}


def normalize(name: str) -> str:
    value = (name or "").strip()
    return _ALIASES.get(value, value.lower())


def make_background(name: str, size=(1920, 1080), layout=None) -> Image.Image:
    preset = normalize(name)
    if preset not in BACKGROUNDS:
        preset = "dusk"
    format_name = layout or ("phone" if size[1] > size[0] else "desktop")
    if format_name not in {"desktop", "phone"}:
        raise ValueError("请选择电脑或手机壁纸.")
    path = Path(__file__).with_name("data") / f"wallpaper-{preset}-{format_name}.png"
    with Image.open(path) as source:
        return ImageOps.fit(source.convert("RGB"), size, Image.Resampling.LANCZOS)
