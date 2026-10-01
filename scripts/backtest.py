"""Walk-forward backtest for one twin, from data already in data/chui.sqlite.

    python scripts/backtest.py specs/cmg.yaml [--from 2017Q1] [--paths 4000] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.evaluation.backtest import TWIN, walk_forward  # noqa: E402
from engine.periods import span  # noqa: E402
from engine.spec import load_spec  # noqa: E402
from storage import db  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--from", dest="first", default=None, help="first test period, e.g. 2017Q1")
    ap.add_argument("--paths", type=int, default=4000)
    ap.add_argument("--json", default=None)
    ap.add_argument("--exclude", action="append", default=[], help='periods left out of scoring, e.g. "2020Q1:2022Q4"')
    args = ap.parse_args()

    rspec = load_spec(args.spec, ROOT / "templates")
    conn = db.connect()
    obs = db.load_observations(conn, [s.series for s in rspec.signals])
    gt = db.load_ground_truth(conn, rspec.ticker)
    ext = db.load_external(conn, rspec.ticker)
    periods = sorted({g.period for g in gt})
    skip: set[str] = set()
    for item in args.exclude:
        a, _, b = item.partition(":")
        skip |= set(span(a, b or a))
    test = [p for p in periods if (args.first is None or p >= args.first) and p not in skip]

    card = walk_forward(rspec, obs, gt, ext, test_periods=test, n_paths=args.paths)
    note = f", excluding {', '.join(args.exclude)}" if args.exclude else ""
    print(f"{rspec.ticker} walk-forward, {len(test)} periods ({test[0]}..{test[-1]}{note}), spec {card.spec_hash[:12]}")
    print(f"{'kpi':14s} {'model':15s} {'n':>3s} {'MAE':>7s} {'RMSE':>7s} {'bias':>7s} {'CRPS':>7s} {'cov80':>6s}")
    for r in card.table():
        cov = f"{r['coverage80']:.2f}" if r["coverage80"] is not None else "   -"
        mark = " *" if r["model"] == TWIN else ""
        print(f"{r['kpi']:14s} {r['model']:15s} {r['n']:3d} {r['mae']:7.2f} {r['rmse']:7.2f} {r['bias']:7.2f} {r['crps']:7.2f} {cov:>6s}{mark}")
    for b in rspec.baselines:
        sk = card.skill(b)
        if any(v is not None for v in sk.values()):
            print(f"CRPS skill vs {b}: " + ", ".join(f"{k} {v:+.2f}" for k, v in sk.items() if v is not None))
    if args.json:
        Path(args.json).write_text(json.dumps({"table": card.table(), "rows": [r.__dict__ for r in card.rows]},
                                              default=str, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
