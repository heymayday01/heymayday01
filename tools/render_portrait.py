#!/usr/bin/env python3
"""
render_portrait.py

Renders a self-drawing ASCII portrait as a standalone SVG.

Two modes:
  1. From a photo:  python tools/render_portrait.py --photo assets/photo-ready.png
     (requires Pillow + numpy from tools/requirements-art.txt)

  2. From a monogram (no photo required):  python tools/render_portrait.py --monogram AT
     Generates a large stylized monogram and renders it as ASCII characters.
     This is the default when no --photo is provided — it produces a striking,
     personal-looking portrait without needing a source image.

The SVG uses SMIL animation: each row is wrapped in a clipping rectangle whose
width animates from 0 to full, staggered row-by-row. The portrait draws itself
in top-to-bottom and then holds.

Usage:
    python tools/render_portrait.py                 # monogram "AT", writes portrait.svg
    python tools/render_portrait.py --monogram ARY  # custom monogram
    python tools/render_portrait.py --photo my.png  # from photo
    PREVIEW=1 python tools/render_portrait.py       # still frame (no animation)
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Character ramp: left = light/empty, right = dense/dark.
GLYPHS = " .,:;~+*xXO#"


# -----------------------------------------------------------------------------
# Source generators
# -----------------------------------------------------------------------------

def monogram_to_grid(letters: str, width: int = 56, height: int = 40) -> list[str]:
    """
    Render the supplied letters as a large monogram and return a 2D grid of
    characters approximating brightness. We draw the letters with PIL at
    a high resolution, then sample down to (width x height) and map each
    pixel to a glyph via GLYPHS.

    Falls back to a built-in 5x7 bitmap font if PIL is unavailable.
    """
    try:
        return _monogram_via_pil(letters, width, height)
    except Exception as e:
        print(f"[portrait] PIL unavailable ({e}); using built-in bitmap font", file=sys.stderr)
        return _monogram_via_bitmap(letters, width, height)


def _monogram_via_pil(letters: str, width: int, height: int) -> list[str]:
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    # Render at high resolution for crisp downsampling
    SCALE = 8
    hi_w, hi_h = width * SCALE, height * SCALE

    img = Image.new("L", (hi_w, hi_h), color=0)  # black background
    draw = ImageDraw.Draw(img)

    # Find the largest font size that fits the letters in the frame
    font = None
    for size in range(hi_h, 8, -2):
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", size
            )
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), letters, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= hi_w * 0.85 and text_h <= hi_h * 0.85:
            break

    # Center the text
    bbox = draw.textbbox((0, 0), letters, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    tx = (hi_w - text_w) // 2 - bbox[0]
    ty = (hi_h - text_h) // 2 - bbox[1]
    draw.text((tx, ty), letters, fill=255, font=font)

    # Downsample to (width, height)
    small = img.resize((width, height), Image.LANCZOS)
    arr = np.array(small)

    # Map brightness 0..255 -> glyph index
    grid: list[str] = []
    for y in range(height):
        row_chars = []
        for x in range(width):
            v = int(arr[y, x])
            # v=0 (black/empty) -> GLYPHS[0] (space), v=255 (white/letter) -> GLYPHS[-1] (dense)
            idx = int(v / 255 * (len(GLYPHS) - 1))
            row_chars.append(GLYPHS[idx])
        grid.append("".join(row_chars))
    return grid


# Built-in 5x7 bitmap font for fallback (no PIL needed)
_BITMAP_FONT = {
    'A': ["01110","10001","10001","11111","10001","10001","10001"],
    'B': ["11110","10001","10001","11110","10001","10001","11110"],
    'C': ["01111","10000","10000","10000","10000","10000","01111"],
    'D': ["11110","10001","10001","10001","10001","10001","11110"],
    'E': ["11111","10000","10000","11110","10000","10000","11111"],
    'F': ["11111","10000","10000","11110","10000","10000","10000"],
    'G': ["01111","10000","10000","10011","10001","10001","01111"],
    'H': ["10001","10001","10001","11111","10001","10001","10001"],
    'I': ["11111","00100","00100","00100","00100","00100","11111"],
    'J': ["00111","00010","00010","00010","00010","10010","01100"],
    'K': ["10001","10010","10100","11000","10100","10010","10001"],
    'L': ["10000","10000","10000","10000","10000","10000","11111"],
    'M': ["10001","11011","10101","10101","10001","10001","10001"],
    'N': ["10001","11001","10101","10011","10001","10001","10001"],
    'O': ["01110","10001","10001","10001","10001","10001","01110"],
    'P': ["11110","10001","10001","11110","10000","10000","10000"],
    'Q': ["01110","10001","10001","10001","10101","10010","01101"],
    'R': ["11110","10001","10001","11110","10100","10010","10001"],
    'S': ["01111","10000","10000","01110","00001","00001","11110"],
    'T': ["11111","00100","00100","00100","00100","00100","00100"],
    'U': ["10001","10001","10001","10001","10001","10001","01110"],
    'V': ["10001","10001","10001","10001","10001","01010","00100"],
    'W': ["10001","10001","10001","10101","10101","11011","10001"],
    'X': ["10001","10001","01010","00100","01010","10001","10001"],
    'Y': ["10001","10001","01010","00100","00100","00100","00100"],
    'Z': ["11111","00001","00010","00100","01000","10000","11111"],
    ' ': ["00000","00000","00000","00000","00000","00000","00000"],
}


def _monogram_via_bitmap(letters: str, width: int = 56, height: int = 40) -> list[str]:
    """Render letters using a 5x7 bitmap font, scaled up to fill the grid."""
    letters = letters.upper()
    # Each letter is 5 wide, 7 tall, plus 1 space between letters
    lw = len(letters) * 6 - 1
    lh = 7

    # Scale to fit the grid
    sx = max(1, width // lw)
    sy = max(1, height // lh)
    s = min(sx, sy)

    # Center the result
    out_w = lw * s
    out_h = lh * s
    pad_x = (width - out_w) // 2
    pad_y = (height - out_h) // 2

    grid = [[' '] * width for _ in range(height)]

    for i, letter in enumerate(letters):
        bitmap = _BITMAP_FONT.get(letter, _BITMAP_FONT[' '])
        for ry in range(7):
            for rx in range(5):
                if bitmap[ry][rx] == '1':
                    # Fill s x s block at (pad_x + (i*6 + rx)*s, pad_y + ry*s)
                    for dy in range(s):
                        for dx in range(s):
                            x = pad_x + (i * 6 + rx) * s + dx
                            y = pad_y + ry * s + dy
                            if 0 <= x < width and 0 <= y < height:
                                grid[y][x] = GLYPHS[-1]

    return ["".join(row) for row in grid]


def photo_to_grid(photo_path: str, width: int = 56, height: int = 40) -> list[str]:
    """Convert a photo to an ASCII grid using brightness mapping."""
    from PIL import Image
    import numpy as np

    img = Image.open(photo_path).convert("L")
    # Preserve aspect ratio: fit into width x height
    img.thumbnail((width, height), Image.LANCZOS)
    arr = np.array(img)

    grid: list[str] = []
    for y in range(arr.shape[0]):
        row_chars = []
        for x in range(arr.shape[1]):
            v = int(arr[y, x])
            # Dark pixel -> dense glyph, light pixel -> space
            idx = int((255 - v) / 255 * (len(GLYPHS) - 1))
            row_chars.append(GLYPHS[idx])
        grid.append("".join(row_chars))
    return grid


# -----------------------------------------------------------------------------
# SVG rendering
# -----------------------------------------------------------------------------

def render_svg(grid: list[str], *, accent: str = "#58A6FF", animate: bool = True) -> str:
    """
    Render the ASCII grid as a self-drawing SVG.
    Each row is wrapped in a clipPath whose width animates from 0 to full.
    """
    if not grid:
        grid = [" " * 40]

    rows = len(grid)
    cols = max(len(r) for r in grid)

    char_w = 9        # pixels per character (mono)
    char_h = 16       # pixels per row
    pad = 24
    width = cols * char_w + pad * 2
    height = rows * char_h + pad * 2

    # Escape XML-special chars in the grid rows
    def esc(s: str) -> str:
        return (s.replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;"))

    # Build rows
    row_svgs: list[str] = []
    for y, row in enumerate(grid):
        row_x = pad
        row_y = pad + y * char_h
        clip_id = f"rowclip-{y}"

        if animate:
            clip_block = f'''
      <clipPath id="{clip_id}">
        <rect x="{row_x}" y="{row_y}" width="0" height="{char_h}">
          <animate attributeName="width" from="0" to="{cols * char_w}" begin="{y * 0.04}s" dur="0.6s" fill="freeze" />
        </rect>
      </clipPath>'''
            text_clip_attr = f' clip-path="url(#{clip_id})"'
        else:
            clip_block = ""
            text_clip_attr = ""

        row_svgs.append(f'''{clip_block}
      <text x="{row_x}" y="{row_y + char_h - 4}" font-family="JetBrains Mono, Menlo, Consolas, monospace" font-size="14" fill="{accent}" letter-spacing="0"{text_clip_attr}>{esc(row)}</text>''')

    rows_joined = "\n".join(row_svgs)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <rect width="{width}" height="{height}" fill="#0D1117" />
{rows_joined}
</svg>'''
    return svg


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a self-drawing ASCII portrait SVG.")
    parser.add_argument("--photo", help="Path to a source photo (PNG/JPG). If omitted, uses --monogram.")
    parser.add_argument("--monogram", default="AT", help="Monogram letters (default: AT)")
    parser.add_argument("--width", type=int, default=56, help="Character grid width")
    parser.add_argument("--height", type=int, default=40, help="Character grid height")
    parser.add_argument("--accent", default="#58A6FF", help="Accent color (default: #58A6FF)")
    parser.add_argument("--out", default="portrait.svg", help="Output SVG path")
    args = parser.parse_args()

    preview = os.environ.get("PREVIEW") == "1"
    animate = not preview

    if args.photo:
        print(f"[portrait] generating grid from photo: {args.photo}")
        grid = photo_to_grid(args.photo, args.width, args.height)
    else:
        print(f"[portrait] generating grid from monogram: {args.monogram}")
        grid = monogram_to_grid(args.monogram, args.width, args.height)

    print(f"[portrait] grid: {len(grid)} rows x {max(len(r) for r in grid)} cols")
    print(f"[portrait] animate={animate}")

    svg = render_svg(grid, accent=args.accent, animate=animate)
    out_path = Path(args.out)
    out_path.write_text(svg)
    print(f"[portrait] wrote {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
