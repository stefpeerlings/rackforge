#!/usr/bin/env python3
"""Generate patch-24.svg with 24 clearly numbered ports."""

ports = []
for row in range(2):
    for col in range(12):
        num = row * 12 + col + 1
        x = 28 + col * 14.5
        y = 13 + row * 14
        ports.append(f'      <rect x="{x:.1f}" y="{y}" width="12" height="10" rx="0.8" fill="#1a1a1e" stroke="#4a4a52" stroke-width="0.5"/>')
        ports.append(f'      <rect x="{x+2.5:.1f}" y="{y+3}" width="7" height="3" rx="0.3" fill="#b8860b" opacity="0.55"/>')
        ports.append(f'      <text x="{x+6:.1f}" y="{y+7.5}" text-anchor="middle" fill="#ccc" font-family="Arial" font-size="3.5" font-weight="bold">{num}</text>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 44" fill="none">
  <rect width="440" height="44" fill="#8a9098"/>
  <rect x="0.5" y="0.5" width="439" height="43" stroke="#6a7078"/>
  <rect x="0" y="0" width="18" height="44" fill="#7a8088"/>
  <circle cx="9" cy="8" r="2.5" fill="#555" stroke="#999" stroke-width="0.5"/>
  <circle cx="9" cy="36" r="2.5" fill="#555" stroke="#999" stroke-width="0.5"/>
  <rect x="422" y="0" width="18" height="44" fill="#7a8088"/>
  <circle cx="431" cy="8" r="2.5" fill="#555" stroke="#999" stroke-width="0.5"/>
  <circle cx="431" cy="36" r="2.5" fill="#555" stroke="#999" stroke-width="0.5"/>
  <rect x="22" y="4" width="396" height="36" rx="1" fill="#9aa0a8" stroke="#707880" stroke-width="0.75"/>
  <text x="220" y="11" text-anchor="middle" fill="#444" font-family="Arial,sans-serif" font-size="5.5" font-weight="bold">24-PORT PATCH PANEL</text>
  <g id="ports">
{chr(10).join(ports)}
  </g>
  <text x="400" y="40" text-anchor="middle" fill="#555" font-family="Arial" font-size="4.5">1–24</text>
</svg>
'''
open("icons/patch-24.svg", "w").write(svg)
print("patch-24.svg written")