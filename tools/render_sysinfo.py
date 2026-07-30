#!/usr/bin/env python3
"""
render_sysinfo.py

Renders a terminal-style "system info" panel as a self-animating SVG.

The panel has a header bar (window controls + title), then a series of
labeled rows. Each row fades + slides in with a small delay so the panel
appears to "type itself out" next to the portrait.

Usage:
    python tools/render_sysinfo.py                 # writes sysinfo.svg
    PREVIEW=1 python tools/render_sysinfo.py       # still frame
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


# Default panel content. Edit freely — the layout adapts.
DEFAULT_ROWS = [
    ("role",    "Systems Engineer"),
    ("focus",   "Kernel  ·  Full-Stack Web  ·  Applied AI"),
    ("stack",   "C  ·  C++  ·  Python  ·  TypeScript  ·  Rust"),
    ("kernel",  "KernelSU  ·  Magisk  ·  AOSP  ·  SD888"),
    ("web",     "Next.js 16  ·  React 19  ·  FastAPI  ·  Prisma"),
    ("ai",      "Gemini  ·  LangGraph  ·  PyTorch  ·  Hugging Face"),
    ("now",     "Building adaptive AI kernel governors"),
    ("location","India  ·  IST (UTC+5:30)"),
    ("status",  "Open to collaboration"),
]


def render_svg(
    rows: list[tuple[str, str]],
    *,
    accent: str = "#58A6FF",
    accent2: str = "#A371F7",
    animate: bool = True,
    title: str = "aryan@profile: ~",
) -> str:
    # Layout constants
    width = 540
    row_h = 32
    header_h = 32
    pad_x = 22
    pad_y_top = header_h + 24
    pad_y_bot = 24
    height = pad_y_top + len(rows) * row_h + pad_y_bot

    # Build rows
    row_svgs: list[str] = []
    for i, (label, value) in enumerate(rows):
        y = pad_y_top + i * row_h
        delay = i * 0.12

        if animate:
            anim_block = f'''
        <animate attributeName="opacity" from="0" to="1" begin="{delay}s" dur="0.4s" fill="freeze" />
        <animateTransform attributeName="transform" type="translate" from="0 8" to="0 0" begin="{delay}s" dur="0.4s" fill="freeze" />'''
        else:
            anim_block = ""

        row_svgs.append(f'''      <g opacity="{'0' if animate else '1'}" transform="{'translate(0 8)' if animate else 'translate(0 0)'}">{anim_block}
        <text x="{pad_x}" y="{y}" font-family="JetBrains Mono, Menlo, Consolas, monospace" font-size="13" fill="{accent2}">{label}</text>
        <text x="{pad_x + 92}" y="{y}" font-family="JetBrains Mono, Menlo, Consolas, monospace" font-size="13" fill="#7D8590">→</text>
        <text x="{pad_x + 116}" y="{y}" font-family="JetBrains Mono, Menlo, Consolas, monospace" font-size="13" fill="#E6EDF3">{value}</text>
      </g>''')

    rows_joined = "\n".join(row_svgs)

    # Window controls (three dots)
    dots_y = header_h / 2
    dots = f'''
    <circle cx="18" cy="{dots_y}" r="5" fill="#FF5F56" />
    <circle cx="36" cy="{dots_y}" r="5" fill="#FFBD2E" />
    <circle cx="54" cy="{dots_y}" r="5" fill="#27C93F" />'''

    # Title (centered)
    title_x = width / 2
    title_y = header_h / 2 + 4

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <defs>
    <linearGradient id="headerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.18" />
      <stop offset="100%" stop-color="{accent2}" stop-opacity="0.18" />
    </linearGradient>
    <linearGradient id="borderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.6" />
      <stop offset="100%" stop-color="{accent2}" stop-opacity="0.6" />
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="{width}" height="{height}" fill="#0D1117" rx="10" ry="10" />
  <!-- Header bar -->
  <rect width="{width}" height="{header_h}" fill="url(#headerGrad)" rx="10" ry="10" />
  <rect y="{header_h - 1}" width="{width}" height="1" fill="{accent}" fill-opacity="0.25" />
  <!-- Window controls -->
  {dots}
  <!-- Title -->
  <text x="{title_x}" y="{title_y}" font-family="JetBrains Mono, Menlo, Consolas, monospace" font-size="12" fill="#7D8590" text-anchor="middle">{title}</text>

  <!-- Rows -->
{rows_joined}

  <!-- Border -->
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" fill="none" stroke="url(#borderGrad)" stroke-width="1" rx="10" ry="10" />
</svg>'''
    return svg


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a terminal-style info panel SVG.")
    parser.add_argument("--accent", default="#58A6FF", help="Primary accent color")
    parser.add_argument("--accent2", default="#A371F7", help="Secondary accent color")
    parser.add_argument("--title", default="aryan@profile: ~", help="Header title")
    parser.add_argument("--out", default="sysinfo.svg", help="Output SVG path")
    args = parser.parse_args()

    preview = os.environ.get("PREVIEW") == "1"
    animate = not preview

    svg = render_svg(DEFAULT_ROWS, accent=args.accent, accent2=args.accent2, animate=animate, title=args.title)
    out_path = Path(args.out)
    out_path.write_text(svg)
    print(f"[sysinfo] wrote {out_path} ({out_path.stat().st_size} bytes, animate={animate})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
