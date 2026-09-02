#!/usr/bin/env python3
"""
Renders contrib-heatmap.svg — a 53-week x 7-day contribution calendar
that reveals diagonally (week-by-week, day-by-day) via staggered CSS
keyframe animations, plus a stats line and a level legend.

Reads data/contributions.json (written by fetch_contributions.py).
If that file doesn't exist, run with DEMO=1 to render a synthetic
dataset — useful for previewing the design before the first real fetch.
"""
import json
import os
import random
from datetime import date, timedelta

WIDTH = 860
CELL = 11
GAP = 3
LEFT_PAD = 34
TOP_PAD = 46
BOTTOM_PAD = 46

BG = "#0d1117"
TEXT = "#c9d1d9"
DIM = "#7d8590"
ACCENT = "#00FF7F"

# level 0..4, brand-tinted (brightest tier = Pedro's accent green)
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", ACCENT]

DOW_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}


def make_demo_data():
    random.seed(7)
    today = date.today()
    start = today - timedelta(days=52 * 7 + today.weekday())
    days = []
    d = start
    while d <= today:
        r = random.random()
        if r < 0.28:
            count = 0
        elif r < 0.55:
            count = random.randint(1, 2)
        elif r < 0.8:
            count = random.randint(3, 5)
        elif r < 0.94:
            count = random.randint(6, 9)
        else:
            count = random.randint(10, 16)
        days.append({"date": d.isoformat(), "count": count})
        d += timedelta(days=1)

    total = sum(x["count"] for x in days)
    best = max(days, key=lambda x: x["count"])
    current_streak = 0
    for x in reversed(days):
        if x["count"] > 0:
            current_streak += 1
        else:
            break
    longest = run = 0
    for x in days:
        if x["count"] > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return {
        "username": "pedrovictormotasilva",
        "days": days,
        "stats": {
            "total_last_year": total,
            "current_streak": current_streak,
            "longest_streak": longest,
            "best_day": {"date": best["date"], "count": best["count"]},
        },
    }


def level_for(count, thresholds=(1, 3, 6, 10)):
    if count <= 0:
        return 0
    for i, t in enumerate(thresholds):
        if count < t:
            return i
    return len(thresholds)


def build_weeks(days):
    by_date = {d["date"]: d["count"] for d in days}
    dates = sorted(by_date)
    if not dates:
        return []
    first = date.fromisoformat(dates[0])
    last = date.fromisoformat(dates[-1])
    start = first - timedelta(days=(first.weekday() + 1) % 7)  # back to Sunday

    weeks = []
    cur = start
    week = []
    while cur <= last:
        count = by_date.get(cur.isoformat(), 0)
        week.append({"date": cur, "count": count, "level": level_for(count)})
        if cur.weekday() == 5:  # Saturday closes the week (Sun-Sat columns)
            weeks.append(week)
            week = []
        cur += timedelta(days=1)
    if week:
        weeks.append(week)
    return weeks[-53:]


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_svg(payload):
    weeks = build_weeks(payload["days"])
    stats = payload.get("stats", {})
    n_weeks = len(weeks)
    grid_w = n_weeks * (CELL + GAP)
    stats_y = TOP_PAD + 7 * (CELL + GAP) + 22
    legend_y = stats_y + 20
    height = legend_y + CELL + 16

    css = f"""
    text {{ font-family: 'Courier New', Menlo, monospace; fill: {TEXT}; }}
    .cell {{
      opacity: 0;
      transform: translate(0, -6px);
      animation: drop 0.5s ease-out forwards;
    }}
    @keyframes drop {{
      to {{ opacity: 1; transform: translate(0, 0); }}
    }}
    .stat-line {{ opacity: 0; animation: fade-up 0.5s ease-out forwards; }}
    @keyframes fade-up {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    """

    body = []

    # header / prompt line
    body.append(
        f'<text x="{LEFT_PAD}" y="20" class="stat-line" '
        f'style="animation-delay:0s" font-size="14" font-weight="bold" '
        f'fill="{ACCENT}">contributions.sh --last-year</text>'
    )

    # grid, diagonal stagger: delay ~ (week_index + day_index) * step
    step = 0.012
    base_delay = 0.35
    max_delay = base_delay
    for wi, week in enumerate(weeks):
        x = LEFT_PAD + wi * (CELL + GAP)
        for di in range(7):
            y = TOP_PAD + di * (CELL + GAP)
            if di < len(week):
                cell = week[di]
                color = PALETTE[cell["level"]]
                delay = base_delay + (wi + di) * step
                max_delay = max(max_delay, delay)
                title = f'{cell["count"]} contributions on {cell["date"].isoformat()}'
                body.append(
                    f'<rect class="cell" style="animation-delay:{delay:.3f}s" '
                    f'x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
                    f'fill="{color}"><title>{esc(title)}</title></rect>'
                )

    # day-of-week labels
    for di, label in DOW_LABELS.items():
        y = TOP_PAD + di * (CELL + GAP) + CELL - 1
        body.append(
            f'<text x="{LEFT_PAD - 8}" y="{y}" text-anchor="end" '
            f'font-size="9" fill="{DIM}">{label}</text>'
        )

    total = stats.get("total_last_year", "?")
    cur_streak = stats.get("current_streak", "?")
    long_streak = stats.get("longest_streak", "?")
    best = stats.get("best_day", {})
    best_txt = f'{best.get("count", "?")} on {best.get("date", "?")}' if best else "?"

    stat_delay = max_delay + 0.12
    stats_text = (
        f"total: {total}   streak: {cur_streak}d   "
        f"longest: {long_streak}d   best day: {best_txt}"
    )
    body.append(
        f'<text x="{LEFT_PAD}" y="{stats_y}" class="stat-line" '
        f'style="animation-delay:{stat_delay:.3f}s" font-size="12" '
        f'fill="{TEXT}">{esc(stats_text)}</text>'
    )

    legend_y = stats_y + 20
    body.append(
        f'<text x="{LEFT_PAD}" y="{legend_y + 8}" class="stat-line" '
        f'style="animation-delay:{stat_delay + 0.1:.3f}s" font-size="10" '
        f'fill="{DIM}">less</text>'
    )
    lx = LEFT_PAD + 32
    for i, color in enumerate(PALETTE):
        body.append(
            f'<rect class="stat-line" style="animation-delay:{stat_delay + 0.1 + i * 0.03:.3f}s" '
            f'x="{lx + i * (CELL + GAP)}" y="{legend_y}" width="{CELL}" height="{CELL}" '
            f'rx="2" fill="{color}"/>'
        )
    body.append(
        f'<text x="{lx + len(PALETTE) * (CELL + GAP) + 6}" y="{legend_y + 8}" '
        f'class="stat-line" style="animation-delay:{stat_delay + 0.25:.3f}s" '
        f'font-size="10" fill="{DIM}">more</text>'
    )

    width = max(WIDTH, LEFT_PAD + grid_w + 20)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}">
  <defs><style>{css}</style></defs>
  <rect x="0" y="0" width="{width}" height="{height}" rx="10" fill="{BG}"/>
  {''.join(body)}
</svg>"""


def main():
    if os.environ.get("DEMO") == "1" or not os.path.exists("data/contributions.json"):
        payload = make_demo_data()
    else:
        with open("data/contributions.json") as f:
            payload = json.load(f)

    svg = build_svg(payload)
    with open("contrib-heatmap.svg", "w") as f:
        f.write(svg)
    print("wrote contrib-heatmap.svg")


if __name__ == "__main__":
    main()
