"""Save today's analyst consensus for every twin's ticker, raw, from each configured provider.

    python scripts/archive_consensus.py            # run by run_daily.py
    python scripts/archive_consensus.py --dry-run  # list providers and tickers, fetch nothing

A provider runs only if its API key variable is set (see adapters/consensus.py); with none set this
prints a note and exits 0, so the daily job is unaffected. One snapshot per provider, ticker and day:
a ticker already saved today is skipped, so reruns do not spend API calls.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.consensus import active_providers, fetch_snapshot  # noqa: E402
from adapters.http import PoliteClient, load_snapshots  # noqa: E402
from scripts.auto_seal import specs  # noqa: E402


def saved_today(source: str, today: str) -> set[str]:
    return {s.params.get("ticker") for s in load_snapshots(source) if s.fetched_at.date().isoformat() == today}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tickers = sorted({r.ticker for r in specs()})
    providers = active_providers()
    if not providers:
        print("consensus: no provider configured (set CHUI_FMP_API_KEY to enable FMP); nothing archived")
        return
    today = datetime.now(timezone.utc).date().isoformat()
    failures = []
    for p in providers:
        done = saved_today(p.name, today)
        todo = [t for t in tickers if t not in done]
        print(f"consensus {p.name}: {len(todo)} to fetch, {len(done)} already saved today")
        if args.dry_run:
            continue
        client = PoliteClient(min_interval_s=p.min_interval_s, max_retries=2)
        for t in todo:
            try:
                snap = fetch_snapshot(p, t, client)
                print(f"  ok   {t:5s} {snap.path}")
            except Exception as e:  # fetch_snapshot already redacts the key
                failures.append(f"{p.name}:{t}")
                print(f"  FAIL {t:5s} {e}")
    if failures:
        print(f"{len(failures)} consensus failures: {failures}")
        sys.exit(1)


if __name__ == "__main__":
    main()
