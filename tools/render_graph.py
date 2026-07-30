#!/usr/bin/env python3
"""
render_graph.py  —  3D floating-tile edition

Renders the contribution grid as elevated tiles with a depth shadow and
a subtle drop-shadow beneath each cell, so the grid looks like a sheet
of floating tiles rather than a flat heat-map.

Animation: tiles fade in column-by-column (a wave), then freeze.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


# Color ramp — matches the hero's blue→purple gradient story
LEVELS = ["#161B22", "#1F6FEB", "#388BFD", "#58A6FF", "#A371F7"]


def render_svg(payload: dict, *, accent: str = "#58A6FF", accent2: str = "#A371F7", animate: bool = True) -> str:
    days = payload.get("days", [])
    stats = payload.get("stats", {})

    days_sorted = sorted(days, key=lambda d: d["date"])
    level_by_date = {d["date"]: d.get("level", 0) for d in days_sorted}

    cols = 52
    rows = 7

    if days_sorted:
        last_date = datetime.strptime(days_sorted[-1]["date"], "%Y-%m-%d").date()
        while last_date.weekday() != 0:
            last_date -= timedelta(days=1)
        first_monday = last_date - timedelta(weeks=51)
    else:
        first_monday = datetime.utcnow().date()

    grid = [[0] * rows for _ in range(cols)]
    for c in range(cols):
        week_start = first_monday + timedelta(weeks=c)
        for r in range(rows):
            d = week_start + timedelta(days=r)
            grid[c][r] = level_by_date.get(d.strftime("%Y-%m-%d"), 0)

    # Layout
    cell = 13
    gap = 4
    elevation = 3       # how much each tile "floats" above its shadow
    pad_left = 40
    pad_top = 36
    pad_right = 20
    pad_bot = 64
    grid_w = cols * (cell + gap) - gap
    grid_h = rows * (cell + gap) - gap
    width = pad_left + grid_w + pad_right
    height = pad_top + grid_h + pad_bot

    # Defs
    defs = f'''  <defs>
    <linearGradient id="cardBorder" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="{accent2}" stop-opacity="0.4"/>
    </linearGradient>
    <linearGradient id="cardHeader" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.1"/>
      <stop offset="100%" stop-color="{accent2}" stop-opacity="0.1"/>
    </linearGradient>
    <filter id="tileShadow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="1.2"/>
      <feOffset dx="0" dy="2"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.5"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="topAccent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0"/>
      <stop offset="50%" stop-color="{accent}" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="{accent2}" stop-opacity="0.8"/>
    </linearGradient>
  </defs>'''

    # Card background
    card_bg = f'''  <rect width="{width}" height="{height}" fill="#0D1117" rx="12" ry="12"/>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" fill="none" stroke="url(#cardBorder)" stroke-width="1" rx="12" ry="12"/>
  <rect width="{width}" height="32" fill="url(#cardHeader)" rx="12" ry="12"/>
  <rect y="31" width="{width}" height="1" fill="{accent}" fill-opacity="0.25"/>
  <rect x="0" y="0" width="{width}" height="2" rx="1" fill="url(#topAccent)"/>'''

    # Title + meta
    title = f'  <text x="{pad_left}" y="20" font-family="JetBrains Mono, monospace" font-size="12" fill="{accent2}">// contribution_graph.svg</text>'
    pulled_at = payload.get("pulled_at", "")[:16].replace("T", " ")
    meta = f'  <text x="{width - pad_right}" y="20" font-family="JetBrains Mono, monospace" font-size="10" fill="#7D8590" text-anchor="end">auto-refreshed · {pulled_at}</text>'

    # Month labels
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    month_svgs = []
    if days_sorted:
        cursor = first_monday
        last_month = -1
        for c in range(cols):
            if cursor.month != last_month:
                x = pad_left + c * (cell + gap)
                month_svgs.append(f'  <text x="{x}" y="{pad_top - 12}" font-family="JetBrains Mono, monospace" font-size="10" fill="#7D8590">{month_names[cursor.month - 1]}</text>')
                last_month = cursor.month
            cursor += timedelta(weeks=1)

    # Day-of-week labels
    dow_svgs = []
    for r, name in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        y = pad_top + r * (cell + gap) + cell - 1
        dow_svgs.append(f'  <text x="{pad_left - 8}" y="{y}" font-family="JetBrains Mono, monospace" font-size="10" fill="#7D8590" text-anchor="end">{name}</text>')

    # Tiles — column-by-column animation
    tile_svgs = []
    for c in range(cols):
        delay = c * 0.025
        col_tiles = []
        for r in range(rows):
            x = pad_left + c * (cell + gap)
            y = pad_top + r * (cell + gap) - elevation
            level = grid[c][r]
            fill = LEVELS[level] if level < len(LEVELS) else LEVELS[0]
            # Shadow beneath (offset down)
            shadow_y = y + elevation
            col_tiles.append(f'      <rect x="{x}" y="{shadow_y}" width="{cell}" height="{cell}" rx="2.5" ry="2.5" fill="#000000" opacity="0.4"/>')
            # Tile itself
            col_tiles.append(f'      <rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" ry="2.5" fill="{fill}" filter="url(#tileShadow)"/>')
        col_block = "\n".join(col_tiles)
        if animate:
            tile_svgs.append(f'  <g opacity="0">\n    <animate attributeName="opacity" from="0" to="1" begin="{delay}s" dur="0.4s" fill="freeze"/>\n{col_block}\n  </g>')
        else:
            tile_svgs.append(f'  <g>\n{col_block}\n  </g>')

    # Stats line
    total = stats.get("total", 0)
    total_label = stats.get("total_label", "contributions")
    current = stats.get("current", 0)
    longest = stats.get("longest", 0)
    busiest = stats.get("busiest_dow", "")
    stats_y = pad_top + grid_h + 32
    stats_text = f"{total} {total_label}  ·  current streak: {current}d  ·  longest: {longest}d  ·  busiest: {busiest}"
    stats_svg = f'  <text x="{pad_left}" y="{stats_y}" font-family="JetBrains Mono, monospace" font-size="11" fill="{accent}">{stats_text}</text>'

    # Legend (right-aligned)
    legend_x = pad_left + grid_w - 5 * (cell + gap) - 70
    legend_y = stats_y - cell
    legend_svgs = [f'  <text x="{legend_x}" y="{legend_y + cell - 1}" font-family="JetBrains Mono, monospace" font-size="10" fill="#7D8590">Less</text>']
    for i in range(5):
        lx = legend_x + 30 + i * (cell + gap)
        legend_svgs.append(f'  <rect x="{lx}" y="{legend_y}" width="{cell}" height="{cell}" rx="2" ry="2" fill="{LEVELS[i]}"/>')
    legend_svgs.append(f'  <text x="{legend_x + 30 + 5 * (cell + gap) + 4}" y="{legend_y + cell - 1}" font-family="JetBrains Mono, monospace" font-size="10" fill="#7D8590">More</text>')

    # Footer accent line
    footer = f'  <rect x="{pad_left}" y="{height - 16}" width="{grid_w}" height="1" fill="{accent}" fill-opacity="0.2"/>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
{defs}
{card_bg}
{title}
{meta}
{chr(10).join(month_svgs)}
{chr(10).join(dow_svgs)}
{chr(10).join(tile_svgs)}
{stats_svg}
{chr(10).join(legend_svgs)}
{footer}
</svg>'''
    return svg


def main() -> int:
    parser = argparse.ArgumentParser(description="Render 3D floating-tile contribution graph SVG.")
    parser.add_argument("--in", dest="in_path", default="assets/contributions.json")
    parser.add_argument("--out", default="graph.svg")
    parser.add_argument("--accent", default="#58A6FF")
    parser.add_argument("--accent2", default="#A371F7")
    args = parser.parse_args()

    in_path = Path(args.in_path)
    if not in_path.exists():
        print(f"[graph] ERROR: {in_path} not found.", file=sys.stderr)
        return 1

    payload = json.loads(in_path.read_text())
    animate = os.environ.get("PREVIEW") != "1"

    svg = render_svg(payload, accent=args.accent, accent2=args.accent2, animate=animate)
    out_path = Path(args.out)
    out_path.write_text(svg)
    print(f"[graph] wrote {out_path} ({out_path.stat().st_size} bytes, animate={animate})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
