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
import subprocess
import sys
import traceback
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import batches  # noqa: E402
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
    for adapter, group in batches(series):  # several series per request where the source allows it
        try:
            snaps = adapter.fetch_many(group, start, end)
            normalized = adapter.normalize(snaps)
            db.save_snapshots(conn, snaps)
        except Exception as e:
            failures.extend(group)
            for name in group:
                print(f"  FAIL {name:34s} {type(e).__name__}: {e}")
            traceback.print_exc(limit=1)
            continue
        for name in group:
            obs = [o for o in normalized if o.series == name]
            if not obs and len(group) > 1:  # a batch can succeed while one of its series returns nothing
                failures.append(name)
                print(f"  FAIL {name:34s} no data in the batch response")
                continue
            db.save_observations(conn, obs)
            print(f"  ok   {name:34s} {len(obs):5d} obs")

    if not args.skip_ground_truth:
        for rspec in specs:
            try:
                print(f"[{rspec.ticker}] ground truth")
                ingest_ground_truth(rspec, conn, date(2012, 1, 1), reparse=False)
            except Exception as e:
                failures.append(f"{rspec.ticker} ground truth")
                print(f"  FAIL {type(e).__name__}: {e}")

    # Save today's analyst consensus raw, if a provider key is set (scripts/archive_consensus.py).
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "archive_consensus.py")])
    if r.returncode != 0:
        failures.append("archive_consensus")

    # Seal each twin's next forecast in the days before its expected release (scripts/auto_seal.py).
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "auto_seal.py")])
    if r.returncode != 0:
        failures.append("auto_seal")

    # Embed Bitcoin proofs into sealed-forecast timestamps once the calendars have them.
    for ots in sorted((ROOT / "forecasts" / "sealed").glob("*.ots")):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "ots.py"), "upgrade", str(ots)], capture_output=True)
        info = subprocess.run([sys.executable, str(ROOT / "scripts" / "ots.py"), "info", str(ots)],
                              capture_output=True, text=True)
        anchored = "BitcoinBlockHeaderAttestation" in info.stdout + info.stderr
        print(f"  ots  {ots.name}: {'anchored in Bitcoin' if anchored else 'pending'}")

    if failures:
        print(f"{len(failures)} failures: {failures}")
        sys.exit(1)


if __name__ == "__main__":
    main()
