#!/usr/bin/env python3
"""Digital patch panel SVGs based on real Keystone / Panduit / Cat6 panels."""

FACE = """  <rect x="2" y="3" width="436" height="36" rx="0.5" fill="#1c1c1c" stroke="#333" stroke-width="0.75"/>"""


def header():
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 44" fill="none">
  <rect width="440" height="44" fill="#0a0a0a"/>
{FACE}
"""


def keystone_slot(x, y, w, h, num):
    return f"""    <text x="{x + w/2:.1f}" y="{y - 2}" text-anchor="middle" fill="#ccc" font-family="Arial,sans-serif" font-size="3.5">{num}</text>
    <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="0.5" fill="#111" stroke="#555" stroke-width="0.6"/>
    <rect x="{x + 1.5:.1f}" y="{y + 1.5:.1f}" width="{w - 3:.1f}" height="{h - 3:.1f}" rx="0.3" fill="#e8e8e8" stroke="#aaa" stroke-width="0.4"/>"""


def rj45_port(x, y, w, h, num, show_num=True):
    num_line = ""
    if show_num:
        num_line = f'    <text x="{x + w/2:.1f}" y="{y + h + 4}" text-anchor="middle" fill="#ddd" font-family="Arial,sans-serif" font-size="3">{num}</text>\n'
    return f"""{num_line}    <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="0.6" fill="#0a0a0a" stroke="#444" stroke-width="0.5"/>
    <rect x="{x + 1:.1f}" y="{y + 1.5:.1f}" width="{w - 2:.1f}" height="{h * 0.55:.1f}" rx="0.3" fill="#1a1a1a"/>
    <rect x="{x + 2:.1f}" y="{y + h * 0.65:.1f}" width="{w - 4:.1f}" height="{h * 0.25:.1f}" rx="0.2" fill="#d4c4a0" opacity="0.85"/>"""


def layout_row(count, y, port_h, section_gaps=None):
    """Full-width port layout in one row. section_gaps: list of col indices after which to add extra gap."""
    left, right = 6, 434
    width = right - left
    section_gaps = section_gaps or []

    if section_gaps:
        extra = len(section_gaps) * 6
        base_gap = 1.5
        port_w = (width - extra - (count - 1) * base_gap) / count
    else:
        base_gap = 2
        port_w = (width - (count - 1) * base_gap) / count

    positions = []
    x = left
    for i in range(count):
        positions.append((x, port_w))
        x += port_w + base_gap
        if i in section_gaps:
            x += 6
    return positions, y, port_h


def gen_16():
    lines = [header(), '  <g id="ports">']
    positions, y, ph = layout_row(16, 14, 14)
    for i, (x, w) in enumerate(positions):
        lines.append(keystone_slot(x, y, w, ph, i + 1))
    lines.append('  </g>')
    lines.append('  <text x="415" y="38" fill="#bbb" font-family="Arial,sans-serif" font-size="4.5">Keystone Panel</text>')
    lines.append("</svg>")
    open("icons/patch-16.svg", "w", encoding="utf-8").write("\n".join(lines))
    print("patch-16.svg (1 row x 16 keystone)")


def gen_24():
    lines = [header()]
    # Label strip above ports
    lines.append('  <rect x="6" y="7" width="428" height="3" fill="#2a2a2a" stroke="#444" stroke-width="0.3"/>')
    lines.append('  <g id="ports">')
    positions, y, ph = layout_row(24, 13, 12, section_gaps=[7, 15])
    for i, (x, w) in enumerate(positions):
        lines.append(rj45_port(x, y, w, ph, i + 1))
    lines.append('  </g>')
    lines.append('  <text x="14" y="40" fill="#ccc" font-family="Arial,sans-serif" font-size="4.5" font-weight="bold">Panduit</text>')
    lines.append('  <text x="420" y="40" text-anchor="end" fill="#ccc" font-family="Arial,sans-serif" font-size="4.5" font-weight="bold">Cat6</text>')
    lines.append("</svg>")
    open("icons/patch-24.svg", "w", encoding="utf-8").write("\n".join(lines))
    print("patch-24.svg (1 row x 24 RJ45, 3x8 groups)")


def gen_48():
    lines = [header(), '  <g id="ports">']
    # 3 sections of 8+8 (top+bottom), gaps between sections
    left, right = 6, 434
    sections = [(26, 120), (126, 220), (226, 414)]  # approximate - compute properly

    section_w = (434 - 6 - 12) / 3  # 12px total gap between 3 sections
    gap = 6
    cols = 8
    port_w = (section_w - (cols - 1) * 1.2) / cols
    port_h = 9
    row_y = [11, 24]

    num = 1
    for sec in range(3):
        sec_left = 6 + sec * (section_w + gap)
        for row in range(2):
            for col in range(8):
                x = sec_left + col * (port_w + 1.2)
                y = row_y[row]
                lines.append(rj45_port(x, y, port_w, port_h, num, show_num=(row == 1)))
                num += 1

    lines.append('  </g>')
    lines.append('  <text x="420" y="40" text-anchor="end" fill="#ccc" font-family="Arial,sans-serif" font-size="4.5" font-weight="bold">Cat 6</text>')
    lines.append("</svg>")
    open("icons/patch-48.svg", "w", encoding="utf-8").write("\n".join(lines))
    print("patch-48.svg (2 rows x 24, 3 sections)")


gen_16()
gen_24()
gen_48()