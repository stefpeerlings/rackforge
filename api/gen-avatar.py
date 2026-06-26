#!/usr/bin/env python3
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent / "icons"
SIZE = 512


def main() -> None:
    img = Image.new("RGB", (SIZE, SIZE), "#0a0f14")
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle((24, 24, 488, 488), radius=80, outline="#2a3f52", width=4, fill="#111a22")
    draw.rounded_rectangle((148, 96, 364, 344), radius=20, outline="#8aa4b8", width=10)
    draw.rounded_rectangle((172, 128, 190, 312), radius=5, fill="#8aa4b8")
    draw.rounded_rectangle((322, 128, 340, 312), radius=5, fill="#8aa4b8")
    draw.rounded_rectangle((188, 148, 324, 192), radius=8, fill="#3d4f5f")
    draw.rounded_rectangle((188, 210, 324, 258), radius=8, fill="#f59e0b")
    draw.rounded_rectangle((188, 276, 324, 320), radius=8, fill="#3d4f5f")
    draw.ellipse((320, 146, 340, 166), fill="#1bdb7a")
    draw.ellipse((320, 286, 340, 306), fill="#3b9eff")
    draw.line((176, 360, 256, 328, 336, 360), fill="#f59e0b", width=10)

    try:
        font = ImageFont.truetype("arial.ttf", 44)
    except OSError:
        font = ImageFont.load_default()

    text = "RackForge"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text(((SIZE - text_w) / 2, 400), text, fill="#f59e0b", font=font)

    png_path = ROOT / "rackforge-avatar.png"
    jpg_path = ROOT / "rackforge-avatar.jpg"
    img.save(png_path, "PNG")
    img.save(jpg_path, "JPEG", quality=92, optimize=True)
    print(f"Wrote {png_path}")
    print(f"Wrote {jpg_path}")


if __name__ == "__main__":
    main()