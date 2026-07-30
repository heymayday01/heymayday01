#!/usr/bin/env python3
"""
pull_contributions.py

Fetches the public GitHub contributions calendar for a user and writes a
JSON file with per-day counts plus streak and day-of-week stats.

No authentication required. Uses the same public HTML endpoint that the
profile page itself consumes:
    https://github.com/users/<username>/contributions

Usage:
    python tools/pull_contributions.py [--user heymayday01] [--out assets/contributions.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from lxml import html as lxml_html


GITHUB_CONTRIB_URL = "https://github.com/users/{user}/contributions"


def fetch_contributions_html(user: str) -> str:
    url = GITHUB_CONTRIB_URL.format(user=user)
    # A real UA helps avoid bot-blocking on some endpoints
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; living-terminal/1.0)",
        "Accept": "text/html,application/xhtml+xml",
    }
    with httpx.Client(timeout=30.0, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def parse_day_cells(html_text: str) -> list[dict]:
    """
    Parse the contribution calendar HTML and return a list of
    {"date": "YYYY-MM-DD", "level": int} dicts.

    GitHub's markup has changed multiple times. As of 2026, day cells are
    <td class="ContributionCalendar-day" data-date="..." data-level="0..4">.
    Older markup used <rect class="day" data-date="..." data-count="...">.

    We prefer data-level when available (0-4 intensity buckets) since the
    raw count attribute has been removed from the public HTML.
    """
    tree = lxml_html.fromstring(html_text)

    days: list[dict] = []

    # Modern td-style cells with data-level (current GitHub markup)
    for td in tree.xpath('//td[contains(@class, "ContributionCalendar-day")]'):
        date = td.get("data-date")
        if not date:
            continue
        # Prefer data-level (0-4) when present
        level_raw = td.get("data-level")
        if level_raw is not None:
            try:
                level = max(0, min(4, int(level_raw)))
            except ValueError:
                level = 0
            # Backwards-compat: keep count attribute name but store the level.
            # (Callers can use 'level' for rendering, 'count' for streak logic.)
            days.append({"date": date, "level": level, "count": level})
            continue
        # Fallback to data-count for older markup
        count_raw = td.get("data-count", "0")
        try:
            count = int(count_raw)
        except ValueError:
            count = 0
        days.append({"date": date, "level": min(4, count), "count": count})

    if days:
        return days

    # Fallback: SVG rect elements (very old markup)
    for rect in tree.xpath('//rect[@class="day"]'):
        date = rect.get("data-date")
        if not date:
            continue
        count_raw = rect.get("data-count", "0")
        try:
            count = int(count_raw)
        except ValueError:
            count = 0
        days.append({"date": date, "level": min(4, count), "count": count})

    return days


def compute_streaks(days: list[dict]) -> dict:
    """Compute current streak, longest streak, and busiest day-of-week."""
    if not days:
        return {"current": 0, "longest": 0, "busiest_dow": None, "total": 0}

    # Sort by date ascending
    sorted_days = sorted(days, key=lambda d: d["date"])

    # Total
    total = sum(d["count"] for d in sorted_days)

    # Compute streaks. A "streak day" is a day with level >= 1.
    # Use date objects so we can detect gaps.
    date_to_level = {d["date"]: d["level"] for d in sorted_days}
    dates = sorted(date_to_level.keys())
    date_objs = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]

    longest = 0
    current_run = 0
    for d in date_objs:
        if date_to_level[d.strftime("%Y-%m-%d")] >= 1:
            current_run += 1
            longest = max(longest, current_run)
        else:
            current_run = 0

    # Current streak: count backward from the most recent day with activity.
    # If today has no activity yet, start from yesterday.
    today = datetime.now(timezone.utc).date()
    current = 0
    cursor = today
    while True:
        key = cursor.strftime("%Y-%m-%d")
        if key in date_to_level and date_to_level[key] >= 1:
            current += 1
            cursor -= timedelta(days=1)
        else:
            # Allow today to be empty (the day isn't over yet) without breaking the streak.
            if cursor == today:
                cursor -= timedelta(days=1)
                continue
            break

    # Busiest day-of-week (0=Mon ... 6=Sun)
    dow_counts = Counter()
    for d in sorted_days:
        if d["level"] > 0:
            dow = datetime.strptime(d["date"], "%Y-%m-%d").weekday()
            dow_counts[dow] += d["level"]
    busiest_dow = dow_counts.most_common(1)[0][0] if dow_counts else None
    dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    busiest_dow_name = dow_names[busiest_dow] if busiest_dow is not None else None

    # Total: count of active days (level >= 1), since raw counts aren't available
    active_days = sum(1 for d in sorted_days if d["level"] >= 1)

    return {
        "current": current,
        "longest": longest,
        "busiest_dow": busiest_dow_name,
        "total": active_days,
        "total_label": "active days",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull GitHub contributions to JSON.")
    parser.add_argument("--user", default="heymayday01", help="GitHub username")
    parser.add_argument("--out", default="assets/contributions.json", help="Output JSON path")
    args = parser.parse_args()

    print(f"[pull] fetching contributions for {args.user} ...")
    html_text = fetch_contributions_html(args.user)
    print(f"[pull] got {len(html_text)} bytes of HTML")

    days = parse_day_cells(html_text)
    print(f"[pull] parsed {len(days)} day cells")

    stats = compute_streaks(days)
    print(f"[pull] total: {stats['total']} | current streak: {stats['current']} | longest: {stats['longest']}")
    if stats["busiest_dow"]:
        print(f"[pull] busiest day-of-week: {stats['busiest_dow']}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "user": args.user,
        "pulled_at": datetime.now(timezone.utc).isoformat(),
        "days": days,
        "stats": stats,
    }

    out_path.write_text(json.dumps(payload, indent=2))
    print(f"[pull] wrote {out_path} ({out_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
