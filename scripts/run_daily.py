"""Daily job: refresh every series used by any spec, then refresh ground truth.

    python scripts/run_daily.py                 # specs/*.yaml and specs/auto/*.yaml, last 400 days
    python scripts/run_daily.py --days 30

Each series is fetched once even when several specs use it (TSA serves every
airline; FRED serves everyone). Raw responses are saved before parsing, so a
day missed by a broken parser can be re-parsed later; a day never fetched cannot.
Schedule with Windows Task Scheduler or cron, e.g. daily at 07:00 local.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import adapter_for  # noqa: E402
from engine.spec import load_spec  # noqa: E402
from scripts.ingest import ingest_ground_truth  # noqa: E402
from storage import db  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=400, help="signal lookback; >365 so revisions and yoy bases refresh")
    ap.add_argument("--skip-ground-truth", action="store_true")
    args = ap.parse_args()

    paths = sorted((ROOT / "specs").glob("*.yaml")) + sorted((ROOT / "specs" / "auto").glob("*.yaml"))
    specs = [load_spec(p, ROOT / "templates") for p in paths]
    conn = db.connect()
    end, start = date.today() + timedelta(days=1), date.today() - timedelta(days=args.days)
    failures = []

    series = sorted({s.series for r in specs for s in r.signals})
    print(f"{len(series)} series across {len(specs)} specs, {start}..{end}")
    for name in series:
        try:
            adapter = adapter_for(name)
            snaps = adapter.fetch(adapter.params_for_series(name), start, end)
            obs = [o for o in adapter.normalize(snaps) if o.series == name]
            db.save_snapshots(conn, snaps)
            db.save_observations(conn, obs)
            print(f"  ok   {name:34s} {len(obs):5d} obs")
        except Exception as e:
            failures.append(name)
            print(f"  FAIL {name:34s} {type(e).__name__}: {e}")
            traceback.print_exc(limit=1)

    if not args.skip_ground_truth:
        for rspec in specs:
            try:
                print(f"[{rspec.ticker}] ground truth")
                ingest_ground_truth(rspec, conn, date(2012, 1, 1), reparse=False)
            except Exception as e:
                failures.append(f"{rspec.ticker} ground truth")
                print(f"  FAIL {type(e).__name__}: {e}")

    if failures:
        print(f"{len(failures)} failures: {failures}")
        sys.exit(1)


if __name__ == "__main__":
    main()
