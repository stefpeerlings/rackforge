import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "icons"


def patch_chassis():
    return """  <defs>
    <linearGradient id="chassis" x1="0" y1="0" x2="0" y2="44" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#222228"/>
      <stop offset="50%" stop-color="#141418"/>
      <stop offset="100%" stop-color="#222228"/>
    </linearGradient>
    <linearGradient id="accentBar" x1="0" y1="0" x2="0" y2="44" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#cbd5e1"/>
      <stop offset="50%" stop-color="#94a3b8"/>
      <stop offset="100%" stop-color="#64748b"/>
    </linearGradient>
  </defs>
  <rect width="440" height="44" fill="url(#chassis)"/>
  <rect x="0.5" y="0.5" width="439" height="43" stroke="#3a3a44" stroke-width="1"/>
  <rect x="2" y="2" width="5" height="40" rx="1" fill="url(#accentBar)"/>
  <rect x="2" y="2" width="5" height="40" rx="1" fill="#fff" opacity="0.08"/>
  <rect x="2" y="3" width="436" height="36" rx="0.5" fill="#1c1c1c" stroke="#333" stroke-width="0.75"/>"""


def port_block(x, y, w, h, gold_y, gold_h=3.0, style="keystone"):
    if style == "keystone":
        return f"""    <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="0.6" fill="#0a0a0a" stroke="#444" stroke-width="0.5"/>
    <rect x="{x + 1:.1f}" y="{y + 1.5:.1f}" width="{w - 2:.1f}" height="{h - 3:.1f}" rx="0.3" fill="#1a1a1a"/>
    <rect x="{x + 2:.1f}" y="{gold_y:.1f}" width="{w - 4:.1f}" height="{gold_h:.1f}" rx="0.2" fill="#d4c4a0" opacity="0.85"/>"""
    return f"""    <rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="0.5" fill="#111" stroke="#555" stroke-width="0.6"/>
    <rect x="{x + 1.5:.1f}" y="{y + 1.5:.1f}" width="{w - 3:.1f}" height="{h - 3:.1f}" rx="0.3" fill="#e8e8e8" stroke="#aaa" stroke-width="0.4"/>"""


def label(cx, y, n, size=3):
    return f'    <text x="{cx:.2f}" y="{y:.1f}" text-anchor="middle" fill="#ddd" font-family="Arial,sans-serif" font-size="{size}">{n}</text>'


def write_svg(name, parts):
    content = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 44" fill="none">\n' + "\n".join(parts) + "\n</svg>\n"
    (ROOT / name).write_text(content, encoding="utf-8")


def gen_patch_24():
    parts = [patch_chassis(), '  <rect x="6" y="7" width="428" height="3" fill="#2a2a2a" stroke="#444" stroke-width="0.3"/>', '  <g id="ports">']
    w, h, step, start_x, start_y = 15.9, 12.0, 17.4, 6.0, 13.0
    for i in range(24):
        x = start_x + i * step
        cx = x + w / 2
        parts.append(port_block(x, start_y, w, h, start_y + 7.8))
        parts.append(label(cx, 29.0, i + 1))
    parts += ['  </g>', '  <text x="420" y="38" text-anchor="end" fill="#bbb" font-family="Arial,sans-serif" font-size="4.5" font-weight="bold">RACK PATCH · 24P</text>']
    write_svg("patch-24.svg", parts)


def gen_patch_16():
    parts = [patch_chassis(), '  <g id="ports">']
    w, h, step, start_x, start_y = 24.9, 14.0, 26.9, 6.0, 14.0
    for i in range(16):
        x = start_x + i * step
        cx = x + w / 2
        parts.append(label(cx, 11.5, i + 1, size=3.5))
        parts.append(port_block(x, start_y, w, h, start_y, style="wide"))
    parts += ['  </g>', '  <text x="420" y="38" text-anchor="end" fill="#bbb" font-family="Arial,sans-serif" font-size="4.5" font-weight="bold">RACK PATCH · 16P</text>']
    write_svg("patch-16.svg", parts)


def gen_patch_48():
    parts = [patch_chassis(), '  <g id="ports">']
    w, h, step, start_x = 16.3, 9.0, 17.5, 6.0
    row_ys = [11.0, 24.0]
    label_ys = [20.0, 37.0]
    for port in range(1, 49):
        col = (port - 1) % 24
        row = (port - 1) // 24
        x = start_x + col * step
        cx = x + w / 2
        y = row_ys[row]
        parts.append(port_block(x, y, w, h, y + 5.9, gold_h=2.2))
        parts.append(label(cx, label_ys[row], port, size=2.8 if port >= 10 else 3))
    parts += ['  </g>', '  <text x="420" y="40" text-anchor="end" fill="#ccc" font-family="Arial,sans-serif" font-size="4.5" font-weight="bold">RACK PATCH · 48P</text>']
    write_svg("patch-48.svg", parts)


if __name__ == "__main__":
    gen_patch_24()
    gen_patch_16()
    gen_patch_48()
    print("Generated patch-16/24/48 SVGs")