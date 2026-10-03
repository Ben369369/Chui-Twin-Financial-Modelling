"""Measure how real shocks decayed, from reported revenue, and write the shock library.

    python scripts/shock_library.py        # writes shocks/library.yaml and prints the table

Two measures, both as percent deviation from a no-shock counterfactual, quarter by quarter:
  revenue: XBRL revenue vs the same quarter of the last pre-event year grown at the pre-event yoy rate
           (same-quarter comparison removes seasonality; levels avoid the yoy base effect).
  comps:   like-for-like level from compounding same-store comps against a flat baseline. Used for
           fast-growing chains, where extrapolating pre-event growth (largely new stores) is not credible.
The trough is the low point within the first year after the event (later lows are other events).
Half-life is fitted from the trough over the next 8 quarters: d_k = d_trough * 0.5 ** (k / half_life).
Scenario presets reuse these half-lives.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.edgar import REVENUE_CONCEPTS, quarterly_facts  # noqa: E402
from adapters.http import load_snapshots, read_raw  # noqa: E402
from engine.periods import shift  # noqa: E402

EVENTS = [
    {"name": "Food-safety crisis", "ticker": "CMG", "cik": "1058090", "event": "2015Q4", "measure": "comps",
     "kpi": "comps", "preset": "Food-safety scare",
     "note": "E. coli and norovirus outbreaks from October 2015; comps-based, pre-event growth (~20%) not extrapolable"},
    {"name": "IT outage", "ticker": "DAL", "cik": "27904", "event": "2024Q3", "trough_window": 1, "fit_quarters": 2,
     "concepts": REVENUE_CONCEPTS, "preset": None,
     "note": "CrowdStrike-triggered outage, July 2024; one-off, so the trough is its own quarter (2025 dip is a separate demand slowdown)"},
    {"name": "Pandemic, airline", "ticker": "DAL", "cik": "27904", "event": "2020Q1",
     "concepts": REVENUE_CONCEPTS, "preset": "Demand slump", "note": "COVID-19"},
    {"name": "Pandemic, hotel", "ticker": "MAR", "cik": "1048286", "event": "2020Q1",
     "concepts": REVENUE_CONCEPTS, "preset": None, "note": "COVID-19"},
    {"name": "Pandemic, restaurant", "ticker": "CMG", "cik": "1058090", "event": "2020Q1",
     "concepts": REVENUE_CONCEPTS, "preset": None, "note": "COVID-19"},
]
HORIZON = 12  # quarters after the event to examine
TROUGH_WINDOW = 4  # the event's own low point falls within its first year
FIT_QUARTERS = 8


def revenue_levels(cik: str, concepts: list[str]) -> dict[str, tuple[float, str]]:
    snaps = sorted((s for s in load_snapshots("edgar") if s.params.get("kind") == "companyfacts"
                    and s.params.get("cik") == str(int(cik))), key=lambda s: s.fetched_at)
    if not snaps:
        raise FileNotFoundError(f"no cached companyfacts for CIK {cik}; run the ingest first")
    facts = quarterly_facts(json.loads(read_raw(snaps[-1])), concepts)
    # Latest filed value per quarter: the best available level (restated if the company restated).
    return {p: (fs[-1].value, f"SEC XBRL accn:{fs[-1].accn} {fs[-1].concept}") for p, fs in facts.items()}


def comps_path(ev: dict) -> tuple[list[tuple[str, float]], list[str]]:
    """Like-for-like level vs the pre-event same quarter: compound comps year over year (flat baseline)."""
    from engine.estimation.calibration import latest_by_period
    from storage import db

    rows = latest_by_period(db.load_ground_truth(db.connect(), ev["ticker"]), ev["ticker"], ev["kpi"])
    e, path, refs = ev["event"], [], []
    for k in range(HORIZON):
        p = shift(e, k)
        chain = [shift(p, -4 * j) for j in range(k // 4 + 1)]
        if not all(c in rows for c in chain):
            break
        level = 1.0
        for c in chain:
            level *= 1 + rows[c].value / 100
            refs.append(rows[c].source_ref.split(" | ")[0])
        path.append((p, level - 1))
    return path, refs


def revenue_path(ev: dict) -> tuple[list[tuple[str, float]], list[str], float]:
    lv = revenue_levels(ev["cik"], ev["concepts"])
    e = ev["event"]
    base = [shift(e, -k) for k in range(4, 0, -1)]  # last pre-event year, by quarter
    prior = [shift(p, -4) for p in base]
    g = sum(math.log(lv[a][0] / lv[b][0]) for a, b in zip(base, prior)) / 4  # pre-event yoy log growth
    path = []
    for k in range(HORIZON):
        p = shift(e, k)
        if p not in lv:
            break
        years, q = divmod(k, 4)
        expected = lv[base[q]][0] * math.exp((years + 1) * g)
        path.append((p, lv[p][0] / expected - 1))
    return path, [lv[p][1] for p, _ in path] + [lv[p][1] for p in base + prior], g


def measure(ev: dict) -> dict:
    if ev.get("measure") == "comps":
        devs, refs = comps_path(ev)
        growth = None
    else:
        devs, refs, g = revenue_path(ev)
        growth = round(100 * (math.exp(g) - 1), 2)
    window = devs[:ev.get("trough_window", TROUGH_WINDOW)]
    trough_i = min(range(len(window)), key=lambda i: window[i][1])
    trough_p, trough = devs[trough_i]
    tail = devs[trough_i:trough_i + ev.get("fit_quarters", FIT_QUARTERS) + 1]
    best = None
    for hl in [x / 20 for x in range(5, 801)]:  # 0.25 to 40 quarters
        sse = sum((d - trough * 0.5 ** (k / hl)) ** 2 for k, (_, d) in enumerate(tail))
        if best is None or sse < best[1]:
            best = (hl, sse)
    recovered = next((p for p, d in tail if d > trough / 2), None)
    return {
        "name": ev["name"], "ticker": ev["ticker"], "event": ev["event"], "note": ev["note"], "preset": ev["preset"],
        "measure": ev.get("measure", "revenue"), "pre_event_yoy_growth_pct": growth,
        "trough_period": trough_p, "trough_deviation_pct": round(100 * trough, 1),
        "quarters_to_trough": trough_i, "half_life_quarters": best[0],
        "half_recovered_by": recovered or f"not within {FIT_QUARTERS} quarters",
        "path_pct": {p: round(100 * d, 1) for p, d in devs},
        "sources": sorted(set(refs)),
        "method": "see scripts/shock_library.py docstring",
    }


def main() -> None:
    out = []
    for ev in EVENTS:
        try:
            m = measure(ev)
        except Exception as e:  # missing raw data for one company must not block the rest
            print(f"{ev['name']} ({ev['ticker']}): skipped, {type(e).__name__}: {e}")
            continue
        out.append(m)
        print(f"{m['name']:22s} {m['ticker']} {m['event']}: trough {m['trough_deviation_pct']:+.1f}% in {m['trough_period']} "
              f"({m['quarters_to_trough']}q after), half-life {m['half_life_quarters']:.2f}q, "
              f"half recovered by {m['half_recovered_by']}")
    path = ROOT / "shocks" / "library.yaml"
    path.parent.mkdir(exist_ok=True)
    path.write_text("# Measured shock profiles. Generated by scripts/shock_library.py; do not edit by hand.\n"
                    + yaml.safe_dump({"shocks": out}, sort_keys=False, width=120), encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
