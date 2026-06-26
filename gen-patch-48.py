#!/usr/bin/env python3
"""Generate patch-48.svg with 48 ports (2 rows x 24)."""

ports = []
for row in range(2):
    for col in range(24):
        num = row * 24 + col + 1
        x = 24 + col * 7.6
        y = 12 + row * 13
        ports.append(f'      <rect x="{x:.1f}" y="{y}" width="6.5" height="9" rx="0.5" fill="#1a1a1e" stroke="#4a4a52" stroke-width="0.4"/>')
        ports.append(f'      <rect x="{x+1.2:.1f}" y="{y+2.5}" width="4" height="2" rx="0.2" fill="#b8860b" opacity="0.5"/>')
        ports.append(f'      <text x="{x+3.2:.1f}" y="{y+7}" text-anchor="middle" fill="#bbb" font-family="Arial" font-size="2.2">{num}</text>')

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
  <text x="220" y="10" text-anchor="middle" fill="#444" font-family="Arial,sans-serif" font-size="5" font-weight="bold">48-PORT PATCH PANEL</text>
  <g id="ports">
{chr(10).join(ports)}
  </g>
  <text x="400" y="40" text-anchor="middle" fill="#555" font-family="Arial" font-size="4">1–48</text>
</svg>
'''
open("icons/patch-48.svg", "w").write(svg)
print("patch-48.svg written")