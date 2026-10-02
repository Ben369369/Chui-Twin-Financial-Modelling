"""Fetch every series a spec maps that has no observations yet, slowly.

    python scripts/fill_missing.py              # all specs, 60 s between rate-limited sources
    python scripts/fill_missing.py --gap 90

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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gap", type=float, default=60.0, help="seconds between requests to slow sources")
    args = ap.parse_args()

    paths = sorted((ROOT / "specs").glob("*.yaml")) + sorted((ROOT / "specs" / "auto").glob("*.yaml"))
    wanted = sorted({s.series for p in paths for s in load_spec(p, ROOT / "templates").signals})
    conn = db.connect()
    have = {r[0] for r in conn.execute("SELECT DISTINCT series FROM observations")}
    missing = [s for s in wanted if s not in have]
    print(f"{len(missing)} of {len(wanted)} series missing: {missing}")
    for i, series in enumerate(missing):
        adapter = adapter_for(series)
        if i and adapter.source in SLOW_SOURCES:
            time.sleep(args.gap)
        try:
            snaps = adapter.fetch(adapter.params_for_series(series), date(2012, 1, 1), date.today() + timedelta(days=1))
            obs = [o for o in adapter.normalize(snaps) if o.series == series]
            db.save_snapshots(conn, snaps)
            db.save_observations(conn, obs)
            print(f"  ok   {series:40s} {len(obs)} obs")
        except Exception as e:
            print(f"  FAIL {series:40s} {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
