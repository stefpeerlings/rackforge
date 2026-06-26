#!/usr/bin/env python3
"""Blanking panels — volledig glad metalen plaat."""

U_H = 40
U_GAP = 2
WIDTH = 440


def total_height(units: int) -> int:
    return units * U_H + (units - 1) * U_GAP


def gen_blank(units: int, filename: str) -> None:
    h = total_height(units)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {h}" fill="none">
  <defs>
    <linearGradient id="metal" x1="0" y1="0" x2="0" y2="{h}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#5a6a78"/>
      <stop offset="12%" stop-color="#4a5866"/>
      <stop offset="30%" stop-color="#3d4d5c"/>
      <stop offset="50%" stop-color="#334155"/>
      <stop offset="70%" stop-color="#3a4a58"/>
      <stop offset="88%" stop-color="#4a5866"/>
      <stop offset="100%" stop-color="#526070"/>
    </linearGradient>
    <linearGradient id="sheen" x1="0" y1="0" x2="{WIDTH}" y2="{h}" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="25%" stop-color="#ffffff" stop-opacity="0.09"/>
      <stop offset="50%" stop-color="#ffffff" stop-opacity="0.02"/>
      <stop offset="75%" stop-color="#ffffff" stop-opacity="0.06"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="{WIDTH}" height="{h}" fill="url(#metal)"/>
  <rect width="{WIDTH}" height="{h}" fill="url(#sheen)"/>
</svg>
"""
    path = f"icons/{filename}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"{filename} ({units}U, {WIDTH}x{h})")


def main():
    gen_blank(1, "blank.svg")
    gen_blank(2, "blank-2u.svg")
    gen_blank(3, "blank-3u.svg")
    gen_blank(4, "blank-4u.svg")
    gen_blank(6, "blank-6u.svg")


if __name__ == "__main__":
    main()