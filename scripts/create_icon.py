"""Generate the project's original calendar/flow icon from vector-like shapes."""
from pathlib import Path

from PIL import Image, ImageDraw


def main():
    root = Path(__file__).resolve().parents[1]
    image = Image.new("RGBA", (512, 512))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 504, 504), radius=120, fill="#4866e8")
    draw.rounded_rectangle((108, 119, 404, 409), radius=44, fill="#ffffff")
    draw.rounded_rectangle((108, 119, 404, 207), radius=35, fill="#cdd8ff")
    draw.rectangle((108, 165, 404, 207), fill="#cdd8ff")
    for x in (182, 330):
        draw.rounded_rectangle((x - 14, 84, x + 14, 155), radius=14, fill="#ffffff")
    for x, y in ((166, 255), (238, 255), (166, 327)):
        draw.rounded_rectangle((x - 18, y - 18, x + 18, y + 18), radius=8, fill="#d3dcf9")
    draw.line([(235, 333), (278, 365), (359, 274)], fill="#1cb695", width=28, joint="curve")
    draw.ellipse((221, 319, 249, 347), fill="#1cb695")
    draw.ellipse((345, 260, 373, 288), fill="#1cb695")
    directory = root / "courseflow" / "data"
    directory.mkdir(parents=True, exist_ok=True)
    image.save(directory / "icon.png")
    image.save(directory / "icon.ico", sizes=[(n, n) for n in (16, 24, 32, 48, 64, 128, 256)])
    print("Generated icon.png and icon.ico")


if __name__ == "__main__":
    main()
