#!/usr/bin/env python3
"""
render_graph.py

Renders an animated contribution-grid SVG from assets/contributions.json.

The grid is drawn as 52 weeks × 7 days of rounded squares. Each square is
colored by its activity level (0-4) using a custom color ramp. Squares
animate in column-by-column (week-by-week) so the graph appears to "wave"
into existence, then freezes.

A legend and a one-line stats summary appear underneath, then the whole
thing freezes.

Usage:
    python tools/render_graph.py                          # reads assets/contributions.json, writes graph.svg
    python tools/render_graph.py --in other.json --out other.svg
    PREVIEW=1 python tools/render_graph.py                # still frame (no animation)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path


# Color ramp for activity levels 0..4.
# Index 0 = no activity (dark), index 4 = top tier (bright).
LEVELS = ["#1a1a2e", "#16537e", "#1c7ed6", "#4dabf7", "#a5d8ff"]

# Alternative blue→purple ramp (matches the banner gradient):
# LEVELS = ["#161b22", "#1f2d4d", "#2b4673", "#58A6FF", "#A371F7"]


def render_svg(
    payload: dict,
    *,
    accent: str = "#58A6FF",
    accent2: str = "#A371F7",
    animate: bool = True,
) -> str:
    days = payload.get("days", [])
    stats = payload.get("stats", {})

    # Group days by ISO week (Monday-based). Each week is a column.
    # Sort by date ascending.
    days_sorted = sorted(days, key=lambda d: d["date"])

    # Build a dict date -> level for quick lookup
    level_by_date = {d["date"]: d.get("level", 0) for d in days_sorted}

    # Determine the set of weeks (columns) to render. We'll render at most
    # the last 52 weeks ending at the most recent day in the data.
    if not days_sorted:
        # Empty graph
        cols = 0
        grid: list[list[int]] = []
    else:
        last_date = datetime.strptime(days_sorted[-1]["date"], "%Y-%m-%d").date()
        # Find the Monday of the week containing last_date
        # Monday = 0, Sunday = 6
        last_monday = last_date
        while last_monday.weekday() != 0:
            last_monday -= __import__("datetime").timedelta(days=1)
        # 52 weeks back
        first_monday = last_monday - __import__("datetime").timedelta(weeks=51)
        cols = 52
        grid: list[list[int]] = [[0] * 7 for _ in range(cols)]
        for c in range(cols):
            week_start = first_monday + __import__("datetime").timedelta(weeks=c)
            for r in range(7):
                d = week_start + __import__("datetime").timedelta(days=r)
                key = d.strftime("%Y-%m-%d")
                grid[c][r] = level_by_date.get(key, 0)

    # Layout
    cell = 12           # square size
    gap = 3             # gap between squares
    pad_left = 36       # left padding for day-of-week labels
    pad_top = 28        # top padding for month labels
    pad_right = 16
    pad_bot = 56        # bottom padding for stats + legend
    cols_visible = cols if cols else 52
    grid_w = cols_visible * (cell + gap) - gap
    grid_h = 7 * (cell + gap) - gap
    width = pad_left + grid_w + pad_right
    height = pad_top + grid_h + pad_bot

    # Month labels along the top
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    month_labels: list[str] = []
    if days_sorted:
        # Walk through columns, emit a month label when the month changes
        from datetime import timedelta
        first_monday_date = datetime.strptime(days_sorted[0]["date"], "%Y-%m-%d").date()
        # Align: find the monday of week 0
        cursor = first_monday_date
        while cursor.weekday() != 0:
            cursor -= timedelta(days=1)
        last_month = -1
        for c in range(cols_visible):
            month = cursor.month
            if month != last_month:
                month_labels.append((c, month_names[month - 1]))
                last_month = month
            cursor += timedelta(weeks=1)

    month_label_svgs = []
    for c, name in month_labels:
        x = pad_left + c * (cell + gap)
        month_label_svgs.append(
            f'    <text x="{x}" y="{pad_top - 10}" font-family="JetBrains Mono, Menlo, Consolas, monospace" font-size="10" fill="#7D8590">{name}</text>'
        )

    # Day-of-week labels (Mon, Wed, Fri shown — typical GitHub layout)
    dow_labels = [(1, "Mon"), (3, "Wed"), (5, "Fri")]
    dow_label_svgs = []
    for r, name in dow_labels:
        y = pad_top + r * (cell + gap) + cell - 1
        dow_label_svgs.append(
            f'    <text x="{pad_left - 8}" y="{y}" font-family="JetBrains Mono, Menlo, Consolas, monospace" font-size="10" fill="#7D8590" text-anchor="end">{name}</text>'
        )

    # Grid squares — animate column-by-column
    square_svgs: list[str] = []
    for c in range(cols_visible):
        # Per-column animation delay (the "wave")
        delay = c * 0.025
        # Use a single <g> per column with opacity animation
        squares_in_col: list[str] = []
        for r in range(7):
            x = pad_left + c * (cell + gap)
            y = pad_top + r * (cell + gap)
            level = grid[c][r] if c < len(grid) else 0
            fill = LEVELS[level] if level < len(LEVELS) else LEVELS[0]
            squares_in_col.append(
                f'      <rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" ry="2" fill="{fill}" />'
            )

        if animate:
            col_block = f'''    <g opacity="0">
      <animate attributeName="opacity" from="0" to="1" begin="{delay}s" dur="0.5s" fill="freeze" />
{chr(10).join(squares_in_col)}
    </g>'''
        else:
            col_block = f'''    <g>
{chr(10).join(squares_in_col)}
    </g>'''
        square_svgs.append(col_block)

    squares_joined = "\n".join(square_svgs)

    # Legend (bottom-right): less → more
    legend_y = pad_top + grid_h + 24
    legend_x = pad_left + grid_w - 5 * (cell + gap) - 80
    legend_svgs = []
    legend_svgs.append(
        f'    <text x="{legend_x}" y="{legend_y + cell - 1}" font-family="JetBrains Mono, Menlo, Consolas, monospace" font-size="10" fill="#7D8590">Less</text>'
    )
    for i in range(5):
        lx = legend_x + 32 + i * (cell + gap)
        legend_svgs.append(
            f'    <rect x="{lx}" y="{legend_y}" width="{cell}" height="{cell}" rx="2" ry="2" fill="{LEVELS[i]}" />'
        )
    legend_svgs.append(
        f'    <text x="{legend_x + 32 + 5 * (cell + gap) + 4}" y="{legend_y + cell - 1}" font-family="JetBrains Mono, Menlo, Consolas, monospace" font-size="10" fill="#7D8590">More</text>'
    )

    # Stats summary (bottom-left)
    total = stats.get("total", 0)
    total_label = stats.get("total_label", "contributions")
    current = stats.get("current", 0)
    longest = stats.get("longest", 0)
    busiest = stats.get("busiest_dow", "")
    stats_text = f"{total} {total_label}  ·  current streak: {current}  ·  longest: {longest}  ·  busiest: {busiest}"
    stats_svg = (
        f'    <text x="{pad_left}" y="{legend_y + cell - 1}" font-family="JetBrains Mono, Menlo, Consolas, monospace" '
        f'font-size="11" fill="{accent}">{stats_text}</text>'
    )

    # Title (top-left)
    title_svg = (
        f'    <text x="{pad_left}" y="16" font-family="JetBrains Mono, Menlo, Consolas, monospace" '
        f'font-size="12" fill="{accent2}">// contribution graph — last 52 weeks</text>'
    )

    # Top-right "auto-refresh" badge
    pulled_at = payload.get("pulled_at", "")
    if pulled_at:
        # Trim to YYYY-MM-DD HH:MM
        pulled_short = pulled_at[:16].replace("T", " ")
    else:
        pulled_short = ""
    refresh_svg = (
        f'    <text x="{width - pad_right}" y="16" font-family="JetBrains Mono, Menlo, Consolas, monospace" '
        f'font-size="10" fill="#7D8590" text-anchor="end">auto-refreshed · {pulled_short}</text>'
    )

    # Footer gradient line
    footer_line = (
        f'    <rect x="{pad_left}" y="{height - 16}" width="{grid_w}" height="1" fill="{accent}" fill-opacity="0.3" />'
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
  <rect width="{width}" height="{height}" fill="#0D1117" />
{title_svg}
{refresh_svg}
{chr(10).join(month_label_svgs)}
{chr(10).join(dow_label_svgs)}
{squares_joined}
{stats_svg}
{chr(10).join(legend_svgs)}
{footer_line}
</svg>'''
    return svg


def main() -> int:
    parser = argparse.ArgumentParser(description="Render contribution graph SVG from JSON.")
    parser.add_argument("--in", dest="in_path", default="assets/contributions.json", help="Input JSON path")
    parser.add_argument("--out", default="graph.svg", help="Output SVG path")
    parser.add_argument("--accent", default="#58A6FF", help="Primary accent color")
    parser.add_argument("--accent2", default="#A371F7", help="Secondary accent color")
    args = parser.parse_args()

    in_path = Path(args.in_path)
    if not in_path.exists():
        print(f"[graph] ERROR: {in_path} not found. Run pull_contributions.py first.", file=sys.stderr)
        return 1

    payload = json.loads(in_path.read_text())
    preview = os.environ.get("PREVIEW") == "1"
    animate = not preview

    print(f"[graph] loaded {len(payload.get('days', []))} days from {in_path}")
    svg = render_svg(payload, accent=args.accent, accent2=args.accent2, animate=animate)

    out_path = Path(args.out)
    out_path.write_text(svg)
    print(f"[graph] wrote {out_path} ({out_path.stat().st_size} bytes, animate={animate})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
