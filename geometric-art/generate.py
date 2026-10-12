"""Geometrik vektor chizma generatori -> geometric.svg (responsive, full screen) + index.html"""
import math, random

W, H = 1600, 900
CX, CY = W / 2, H / 2
random.seed(7)


def hsl(h, s, l, a=1.0):
    return f"hsla({h % 360:.0f},{s}%,{l}%,{a:.3f})"


out = []
add = out.append
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" height="100%" '
    f'preserveAspectRatio="xMidYMid slice" shape-rendering="geometricPrecision">')
add('''<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#060a1a"/><stop offset=".55" stop-color="#14123a"/><stop offset="1" stop-color="#0b2a4a"/>
  </linearGradient>
  <radialGradient id="core" cx="50%" cy="50%" r="50%">
    <stop offset="0" stop-color="#22d3ee" stop-opacity=".45"/><stop offset=".5" stop-color="#8b5cf6" stop-opacity=".16"/><stop offset="1" stop-color="#8b5cf6" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#67e8f9"/><stop offset="1" stop-color="#f472b6"/>
  </linearGradient>
</defs>''')
add(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')

# 1) uchburchak panjara (tessellation)
s = 100.0
h = s * math.sqrt(3) / 2
rows = int(H / h) + 3
cols = int(W / s) + 3
pts = {}
for r in range(-1, rows + 1):
    for c in range(-2, cols + 3):
        pts[(r, c)] = (c * s + (s / 2 if r % 2 else 0), r * h)
tri = []
for r in range(-1, rows):
    for c in range(-2, cols + 2):
        a, b = pts[(r, c)], pts[(r, c + 1)]
        if r % 2 == 0:
            d, e = pts[(r + 1, c)], pts[(r + 1, c + 1)]
            tri += [(a, b, d), (d, e, b)]
        else:
            d, e = pts[(r + 1, c + 1)], pts[(r + 1, c)]
            tri += [(a, b, d), (a, d, e)]
add('<g stroke="#ffffff" stroke-opacity=".07" stroke-width="1">')
for t in tri:
    mx = sum(p[0] for p in t) / 3
    my = sum(p[1] for p in t) / 3
    dist = min(1.0, math.hypot(mx - CX, my - CY) / math.hypot(CX, CY))
    hue = 190 + 150 * (mx / W) + 30 * (my / H)
    op = max(0.0, 0.34 * (1 - dist) ** 1.4) * random.uniform(0.35, 1.0)
    pts_s = " ".join(f"{x:.1f},{y:.1f}" for x, y in t)
    add(f'<polygon points="{pts_s}" fill="{hsl(hue, 85, 60, op)}"/>')
add('</g>')

add(f'<circle cx="{CX}" cy="{CY}" r="560" fill="url(#core)"/>')

# 2) konsentrik doiralar
for i, r in enumerate(range(110, 470, 40)):
    add(f'<circle cx="{CX}" cy="{CY}" r="{r}" fill="none" stroke="#a5f3fc" stroke-opacity="{0.22 - i * 0.015:.3f}" stroke-width="1"/>')

# 3) aylangan kvadratlar mandalasi
n = 30
for i in range(n):
    ang = i * (90 / n) * 1.0
    size = 400 * (1 - i / (n * 1.18))
    hue = 185 + i * (170 / n)
    add(f'<rect x="{CX - size:.1f}" y="{CY - size:.1f}" width="{2 * size:.1f}" height="{2 * size:.1f}" '
        f'fill="none" stroke="{hsl(hue, 90, 66, 0.85)}" stroke-width="1.6" '
        f'transform="rotate({ang:.2f} {CX} {CY})"/>')

# 4) ikki qarama-qarshi muntazam uchburchaklar (olti burchakli yulduz) va olti burchak
def poly(n_sides, r, rot=0):
    return [(CX + r * math.cos(math.radians(rot + k * 360 / n_sides)),
             CY + r * math.sin(math.radians(rot + k * 360 / n_sides))) for k in range(n_sides)]

for r, rot, col, w in [(300, -90, "#f472b6", 2.2), (300, 90, "#67e8f9", 2.2),
                       (190, -90, "#fde68a", 1.8), (190, 90, "#a78bfa", 1.8)]:
    p = " ".join(f"{x:.1f},{y:.1f}" for x, y in poly(3, r, rot))
    add(f'<polygon points="{p}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linejoin="round" stroke-opacity=".9"/>')
p = " ".join(f"{x:.1f},{y:.1f}" for x, y in poly(6, 150, 0))
add(f'<polygon points="{p}" fill="rgba(34,211,238,.08)" stroke="url(#ring)" stroke-width="2.4" stroke-linejoin="round"/>')

# 5) markaz va nurlar
for k in range(24):
    a = math.radians(k * 15)
    r1, r2 = 70, 112 if k % 2 == 0 else 92
    add(f'<line x1="{CX + r1 * math.cos(a):.1f}" y1="{CY + r1 * math.sin(a):.1f}" '
        f'x2="{CX + r2 * math.cos(a):.1f}" y2="{CY + r2 * math.sin(a):.1f}" stroke="#ecfeff" stroke-opacity=".75" stroke-width="1.6" stroke-linecap="round"/>')
add(f'<circle cx="{CX}" cy="{CY}" r="58" fill="none" stroke="url(#ring)" stroke-width="3"/>')
add(f'<circle cx="{CX}" cy="{CY}" r="9" fill="#ecfeff"/>')

# 6) burchaklardagi ramka chiziqlari
m = 36
L = 120
for (x, y, dx, dy) in [(m, m, 1, 1), (W - m, m, -1, 1), (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
    add(f'<path d="M{x + dx * L} {y} H{x} V{y + dy * L}" fill="none" stroke="#67e8f9" stroke-opacity=".7" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>')
add('</svg>')
svg = "\n".join(out)
open("geometric.svg", "w").write(svg)
open("index.html", "w").write(
    '<!doctype html>\n<html lang="uz"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    '<title>Geometrik chizma</title>'
    '<style>html,body{margin:0;height:100%;background:#060a1a;overflow:hidden}'
    'svg{display:block;width:100vw;height:100vh;height:100dvh}</style></head><body>\n'
    + svg + '\n</body></html>\n')
print("ok", len(svg) // 1024, "KB")
