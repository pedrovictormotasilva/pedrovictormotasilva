#!/usr/bin/env python3
"""
Fetches the public contribution calendar for a GitHub user WITHOUT any
token/auth — GitHub serves it as plain HTML at:
    https://github.com/users/<username>/contributions

Writes data/contributions.json with the raw per-day counts plus a few
derived stats (current streak, longest streak, best day, monthly totals)
that render_heatmap_svg.py turns into the animated SVG.

Runs daily via .github/workflows/update-profile-art.yml.
"""
import json
import os
import sys
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GITHUB_PROFILE_USER", "pedrovictormotasilva")
URL = f"https://github.com/users/{USERNAME}/contributions"


def fetch_days():
    resp = requests.get(
        URL,
        headers={"User-Agent": "Mozilla/5.0 (profile-readme-bot)"},
        timeout=20,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    days = []
    # GitHub renders each day as a <td> (older markup) or an svg <rect>
    # (newer markup) tagged with data-date / data-level or data-count.
    cells = soup.select("td.ContributionCalendar-day, rect.ContributionCalendar-day")
    for cell in cells:
        d = cell.get("data-date")
        if not d:
            continue
        level = cell.get("data-level")
        count_attr = cell.get("data-count")
        tooltip_id = cell.get("id")
        count = None
        if count_attr is not None:
            try:
                count = int(count_attr)
            except ValueError:
                count = None
        days.append({
            "date": d,
            "level": int(level) if level is not None else None,
            "count": count,
            "tooltip_id": tooltip_id,
        })

    # Tooltips (older markup) carry the human-readable "N contributions on ..."
    # text with the actual count; map them back onto days missing a count.
    tooltips = soup.select("tool-tip[for]")
    tip_by_id = {t.get("for"): t.get_text(strip=True) for t in tooltips}
    for d in days:
        if d["count"] is None and d["tooltip_id"] in tip_by_id:
            text = tip_by_id[d["tooltip_id"]]
            first_tok = text.split(" ", 1)[0].replace(",", "")
            d["count"] = 0 if text.lower().startswith("no contributions") else _safe_int(first_tok)
        d.pop("tooltip_id", None)

    days = [d for d in days if d["count"] is not None]
    days.sort(key=lambda d: d["date"])
    return days


def _safe_int(s):
    try:
        return int(s)
    except ValueError:
        return 0


def compute_stats(days):
    if not days:
        return {}

    total = sum(d["count"] for d in days)
    best = max(days, key=lambda d: d["count"])

    current_streak = 0
    for d in reversed(days):
        if d["count"] > 0:
            current_streak += 1
        else:
            break

    longest_streak = 0
    run = 0
    for d in days:
        if d["count"] > 0:
            run += 1
            longest_streak = max(longest_streak, run)
        else:
            run = 0

    monthly = {}
    for d in days:
        month = d["date"][:7]
        monthly[month] = monthly.get(month, 0) + d["count"]

    return {
        "total_last_year": total,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly_totals": monthly,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def main():
    days = fetch_days()
    if not days:
        print("warning: no contribution days parsed, GitHub markup may have "
              "changed — leaving previous data/contributions.json untouched",
              file=sys.stderr)
        sys.exit(0)

    payload = {
        "username": USERNAME,
        "days": days,
        "stats": compute_stats(days),
    }

    os.makedirs("data", exist_ok=True)
    with open("data/contributions.json", "w") as f:
        json.dump(payload, f, indent=2)
    print(f"wrote data/contributions.json ({len(days)} days, "
          f"total={payload['stats'].get('total_last_year')})")


if __name__ == "__main__":
    main()
