"""Fetch every series a spec maps that has no observations yet, slowly.

    python scripts/fill_missing.py              # all specs, 60 s between rate-limited sources
    python scripts/fill_missing.py --gap 90
    python scripts/fill_missing.py --stale 3    # also refetch series whose latest point is over 3 days old

Useful after a batch where a rate-limited source (GDELT) refused some requests.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import adapter_for  # noqa: E402
from engine.spec import load_spec  # noqa: E402
from storage import db  # noqa: E402

SLOW_SOURCES = {"gdelt"}
MIN_HISTORY_DAYS = 365


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=float, default=60.0, help="seconds between requests to slow sources")
    ap.add_argument("--stale", type=int, default=None,
                    help="also refetch series whose latest observation is more than this many days old")
    args = ap.parse_args()

    paths = sorted((ROOT / "specs").glob("*.yaml")) + sorted((ROOT / "specs" / "auto").glob("*.yaml"))
    wanted = sorted({s.series for p in paths for s in load_spec(p, ROOT / "templates").signals})
    conn = db.connect()
    # A series counts as present only with at least MIN_HISTORY_DAYS of history: a daily run's short
    # window can create a first, partial slice that would otherwise hide the gap.
    spans = {r[0]: (date.fromisoformat(r[1]), date.fromisoformat(r[2]))
             for r in conn.execute("SELECT series, MIN(observed_at), MAX(observed_at) FROM observations GROUP BY series")}
    missing = [s for s in wanted if s not in spans or (spans[s][1] - spans[s][0]).days < MIN_HISTORY_DAYS]
    # Stale: history is fine but stops early (e.g. a rate-limited daily run). Refetch only the recent tail.
    stale = {} if args.stale is None else {
        s: spans[s][1] - timedelta(days=30) for s in wanted
        if s not in missing and s in spans and (date.today() - spans[s][1]).days > args.stale}
    print(f"{len(missing)} of {len(wanted)} series missing or short: {missing}")
    if args.stale is not None:
        print(f"{len(stale)} stale (latest point over {args.stale} days old): {sorted(stale)}")
    missing += sorted(stale)
    for i, series in enumerate(missing):
        adapter = adapter_for(series)
        if i and adapter.source in SLOW_SOURCES:
            time.sleep(args.gap)
        try:
            start = stale.get(series, date(2012, 1, 1))
            snaps = adapter.fetch(adapter.params_for_series(series), start, date.today() + timedelta(days=1))
            obs = [o for o in adapter.normalize(snaps) if o.series == series]
            db.save_snapshots(conn, snaps)
            db.save_observations(conn, obs)
            print(f"  ok   {series:40s} {len(obs)} obs")
        except Exception as e:
            print(f"  FAIL {series:40s} {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
