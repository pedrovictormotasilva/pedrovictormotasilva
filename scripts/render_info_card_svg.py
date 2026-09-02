#!/usr/bin/env python3
"""
Generates info-card.svg — a neofetch-style terminal panel that "prints"
itself: each line fades + slides in with a staggered delay, finishing
with a blinking cursor. Self-contained (no JS), pure CSS keyframes,
so it animates natively when GitHub renders the SVG in a README.

Run with STATIC=1 to freeze the last animation frame (useful for a
quick static PNG-less preview / thumbnail).
"""
import os

ACCENT = "#00FF7F"
BG = "#0d1117"
BORDER = "#00FF7F"
DIM = "#7d8590"
TEXT = "#c9d1d9"

WIDTH = 490
HEIGHT = 340
PAD_X = 26
LINE_H = 27
TOP = 64

# label, value
ROWS = [
    ("user", "pedro@github"),
    ("os", "Brazil \U0001F1E7\U0001F1F7"),
    ("age", "19"),
    ("role", "Flutter Developer"),
    ("focus", "Mobile App Development"),
    ("studying", "Backend Development"),
    ("building", "SaaS & Mobile Apps"),
    ("shell", "dart / flutter / react"),
]

STATIC = os.environ.get("STATIC") == "1"


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_svg() -> str:
    css_lines = []
    body_lines = []

    header_delay = 0.15
    row_start_delay = 0.55
    row_stagger = 0.16

    css_lines.append(f"""
    .card-border {{
      stroke-dasharray: 1600;
      stroke-dashoffset: 1600;
      animation: draw 1.1s ease-out forwards;
    }}
    @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}

    .line {{
      opacity: 0;
      transform: translateX(-14px);
      animation: type-in 0.5s ease-out forwards;
    }}
    @keyframes type-in {{
      to {{ opacity: 1; transform: translateX(0); }}
    }}

    .cursor {{
      opacity: 0;
      animation: cursor-in 0.3s ease-out forwards, blink 1s step-end infinite;
    }}
    @keyframes cursor-in {{ to {{ opacity: 1; }} }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    """)

    if STATIC:
        css_lines.append("""
        .card-border { stroke-dashoffset: 0; animation: none; }
        .line { opacity: 1; transform: translateX(0); animation: none; }
        .cursor { opacity: 1; animation: none; }
        """)

    # header prompt line
    body_lines.append(
        f'<text x="{PAD_X}" y="40" class="line" '
        f'style="animation-delay:{header_delay}s" '
        f'font-family="\'Courier New\', monospace" font-size="17" '
        f'font-weight="bold" fill="{ACCENT}">'
        f'pedro@github ~ %</text>'
    )
    body_lines.append(
        f'<line x1="{PAD_X}" y1="50" x2="{WIDTH - PAD_X}" y2="50" '
        f'stroke="{DIM}" stroke-opacity="0.35" class="line" '
        f'style="animation-delay:{header_delay + 0.1}s"/>'
    )

    y = TOP
    for i, (label, value) in enumerate(ROWS):
        delay = row_start_delay + i * row_stagger
        body_lines.append(
            f'<text x="{PAD_X}" y="{y}" class="line" '
            f'style="animation-delay:{delay:.2f}s" '
            f'font-family="\'Courier New\', monospace" font-size="15" '
            f'fill="{DIM}">{esc(label)}</text>'
        )
        body_lines.append(
            f'<text x="{PAD_X + 118}" y="{y}" class="line" '
            f'style="animation-delay:{delay:.2f}s" '
            f'font-family="\'Courier New\', monospace" font-size="15" '
            f'font-weight="bold" fill="{TEXT}">{esc(value)}</text>'
        )
        y += LINE_H

    cursor_delay = row_start_delay + len(ROWS) * row_stagger + 0.1
    body_lines.append(
        f'<text x="{PAD_X}" y="{y + 4}" class="cursor" '
        f'style="animation-delay:{cursor_delay:.2f}s" '
        f'font-family="\'Courier New\', monospace" font-size="15" '
        f'fill="{ACCENT}">pedro@github ~ % _</text>'
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
     viewBox="0 0 {WIDTH} {HEIGHT}" font-family="'Courier New', monospace">
  <defs>
    <style>{''.join(css_lines)}</style>
  </defs>
  <rect x="0" y="0" width="{WIDTH}" height="{HEIGHT}" rx="10" fill="{BG}"/>
  <rect x="1.5" y="1.5" width="{WIDTH - 3}" height="{HEIGHT - 3}" rx="9"
        fill="none" stroke="{BORDER}" stroke-width="1.4" opacity="0.8"
        class="card-border"/>
  <circle cx="20" cy="18" r="5" fill="#ff5f56"/>
  <circle cx="38" cy="18" r="5" fill="#ffbd2e"/>
  <circle cx="56" cy="18" r="5" fill="#27c93f"/>
  {''.join(body_lines)}
</svg>"""
    return svg


if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "..", "info-card.svg")
    with open(out_path, "w") as f:
        f.write(build_svg())
    print(f"wrote {out_path}")
