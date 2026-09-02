#!/usr/bin/env python3
"""
Converts a photo into a self-typing ASCII-art SVG portrait.

Pipeline:
  1. Remove the background (rembg) so only the subject remains.
  2. Composite onto pure white.
  3. Crop tightly to the subject's bounding box.
  4. CLAHE contrast boost (OpenCV) so the ASCII ramp has more range to work with.
  5. Downsample to a character grid; map brightness -> density-ramp glyph.
  6. Emit an SVG where each row is wrapped in a clip-path that animates
     left-to-right (a "typing" wipe), staggered row by row via CSS.

Local-only step (uses rembg / opencv / numpy) — the daily GitHub Action
does NOT need to re-run this; the ASCII portrait is generated once from
a chosen photo and committed like a normal asset.
"""
import argparse
import io
import os

import numpy as np
from PIL import Image

RAMP = " .`:-=+*cs#%@"  # bright -> dark

ACCENT = "#00FF7F"
BG = "#0d1117"


def remove_background(img: Image.Image) -> Image.Image:
    from rembg import remove, new_session
    session = new_session("u2netp")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    out = remove(buf.getvalue(), session=session)
    return Image.open(io.BytesIO(out)).convert("RGBA")


def composite_on_white(rgba: Image.Image) -> Image.Image:
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, rgba).convert("RGB")


def isolate_main_subject(rgba: Image.Image) -> Image.Image:
    """Keep only the largest connected foreground blob — drops stray
    flecks the background-removal model leaves floating nearby (bits of
    background it misclassified as foreground)."""
    import cv2
    alpha = np.array(rgba.split()[-1])
    mask = (alpha > 20).astype(np.uint8)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num <= 1:
        return rgba
    areas = stats[1:, cv2.CC_STAT_AREA]  # skip background label 0
    largest = 1 + int(np.argmax(areas))
    keep = labels == largest
    new_alpha = np.where(keep, alpha, 0).astype(np.uint8)
    out = rgba.copy()
    r, g, b, _ = out.split()
    out = Image.merge("RGBA", (r, g, b, Image.fromarray(new_alpha)))
    return out


def crop_to_subject(rgba: Image.Image, pad_frac: float = 0.08) -> tuple[Image.Image, tuple]:
    rgba = isolate_main_subject(rgba)
    alpha = np.array(rgba.split()[-1])
    ys, xs = np.where(alpha > 20)
    if len(xs) == 0:
        return rgba, (0, 0, rgba.width, rgba.height)
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    w, h = x1 - x0, y1 - y0
    padx, pady = int(w * pad_frac), int(h * pad_frac)
    x0 = max(0, x0 - padx)
    y0 = max(0, y0 - pady)
    x1 = min(rgba.width, x1 + padx)
    y1 = min(rgba.height, y1 + pady)
    return rgba.crop((x0, y0, x1, y1)), (x0, y0, x1, y1)


def clahe_contrast(gray_img: Image.Image) -> Image.Image:
    import cv2
    arr = np.array(gray_img)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    out = clahe.apply(arr)
    return Image.fromarray(out)


def brightness_to_grid(gray_img: Image.Image, cols: int, char_aspect: float = 0.52):
    w, h = gray_img.size
    rows = max(1, round(cols * (h / w) * char_aspect))
    small = gray_img.resize((cols, rows), Image.LANCZOS)
    arr = np.array(small).astype(np.float32)
    idx = ((255 - arr) / 255 * (len(RAMP) - 1)).round().astype(int)
    idx = np.clip(idx, 0, len(RAMP) - 1)
    lines = ["".join(RAMP[v] for v in row) for row in idx]
    return lines, rows


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(lines, font_size=6.6, char_w_ratio=0.6, line_h_ratio=1.0,
              target_width=370, stagger=0.045, wipe_dur=0.55, start_delay=0.25):
    cols = max(len(l) for l in lines) if lines else 0
    char_w = font_size * char_w_ratio
    line_h = font_size * line_h_ratio
    content_w = cols * char_w
    scale = target_width / content_w if content_w else 1
    font_size *= scale
    char_w *= scale
    line_h *= scale

    pad = 14
    width = round(cols * char_w + pad * 2)
    height = round(len(lines) * line_h + pad * 2)

    css = f"""
    text {{
      font-family: 'Courier New', Menlo, monospace;
      font-size: {font_size:.2f}px;
      fill: {ACCENT};
      white-space: pre;
    }}
    .row {{
      clip-path: inset(0 100% 0 0);
      animation: wipe {wipe_dur}s steps(28, end) forwards;
    }}
    @keyframes wipe {{
      to {{ clip-path: inset(0 0% 0 0); }}
    }}
    """

    body = []
    for i, line in enumerate(lines):
        y = pad + (i + 1) * line_h - line_h * 0.28
        delay = start_delay + i * stagger
        body.append(
            f'<g class="row" style="animation-delay:{delay:.3f}s">'
            f'<text x="{pad}" y="{y:.1f}" xml:space="preserve">{esc(line)}</text>'
            f'</g>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}">
  <defs><style>{css}</style></defs>
  <rect x="0" y="0" width="{width}" height="{height}" fill="{BG}"/>
  {''.join(body)}
</svg>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo", help="path to source photo")
    ap.add_argument("-o", "--out", default="avi-ascii.svg")
    ap.add_argument("--cols", type=int, default=92)
    ap.add_argument("--width", type=int, default=370)
    args = ap.parse_args()

    img = Image.open(args.photo).convert("RGB")
    print("removing background...")
    rgba = remove_background(img)
    cropped_rgba, bbox = crop_to_subject(rgba)
    print("crop bbox:", bbox)
    composited = composite_on_white(cropped_rgba)
    gray = composited.convert("L")
    gray = clahe_contrast(gray)
    lines, rows = brightness_to_grid(gray, cols=args.cols)
    print(f"grid {args.cols}x{rows}")
    svg = build_svg(lines, target_width=args.width)
    with open(args.out, "w") as f:
        f.write(svg)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
