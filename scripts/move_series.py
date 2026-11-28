"""Move signals from one source's copy of a series to the publisher's own, safely.

    python scripts/move_series.py check            # parity of every move whose two series are both stored
    python scripts/move_series.py apply            # rename in specs and catalogs, only moves that pass
    python scripts/move_series.py apply --dry-run

Moves are listed in adapters/series_moves.yaml (old name: new name). A move passes when the two series agree on at least
MIN_SHARE of their common periods within REL_TOL, and the new series covers the old one's history
from 2012, missing at most 0.5% of the old series' periods. `apply` rewrites exact series names in the hand
specs, auto specs, industry packs, the series catalog and the dashboard. Experiment specs are records
of past runs and stay as they are. Rerun the backtests afterwards and report any change.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import moved_series  # noqa: E402
from storage import db  # noqa: E402

MOVES = moved_series()
REL_TOL = 1e-3
MIN_SHARE = 0.99
MAX_GAP_SHARE = 0.005
HISTORY_FROM = date(2012, 1, 1)
FILES = ["specs/*.yaml", "specs/auto/*.yaml", "onboarding/industry_packs.yaml", "adapters/series_catalog.yaml",
         "web/src/*.tsx"]


def series_values(conn, name: str) -> dict[str, float]:
    return dict(conn.execute("SELECT observed_at, value FROM observations WHERE series = ?", (name,)).fetchall())


def check(conn, old: str, new: str) -> tuple[bool, str]:
    a, b = series_values(conn, old), series_values(conn, new)
    if not a or not b:
        return False, f"missing data (old {len(a)} rows, new {len(b)} rows)"
    common = sorted(set(a) & set(b))
    if not common:
        return False, "no common periods"
    close = [d for d in common if abs(a[d] - b[d]) <= REL_TOL * max(abs(a[d]), 1e-9)]
    share = len(close) / len(common)
    worst = max(common, key=lambda d: abs(a[d] - b[d]) / max(abs(a[d]), 1e-9))
    only_old = sorted(d for d in set(a) - set(b) if d >= HISTORY_FROM.isoformat() and d <= max(b))
    note = (f"{len(common)} common periods, {share:.1%} within {REL_TOL:.1%}; worst {worst}: "
            f"{a[worst]} vs {b[worst]}; new from {min(b)}; old-only periods since {HISTORY_FROM.year}: "
            f"{len(only_old)} {only_old[:4]}")
    first_needed = min((d for d in a if d >= HISTORY_FROM.isoformat()), default=min(a))
    ok = (share >= MIN_SHARE and min(b) <= first_needed
          and len(only_old) <= max(2, MAX_GAP_SHARE * len(common)))  # a few missing trading days are fine
    return ok, note


def apply(moves: dict[str, str], dry_run: bool) -> None:
    paths = sorted({p for pattern in FILES for p in ROOT.glob(pattern)})
    for p in paths:
        text = p.read_bytes().decode("utf-8")  # bytes: keep line endings
        new = text
        for old, repl in moves.items():
            new = re.sub(rf"(?<![\w:.]){re.escape(old)}(?![\w.])", repl, new)
        if new != text:
            n = sum(len(re.findall(rf"(?<![\w:.]){re.escape(o)}(?![\w.])", text)) for o in moves)
            print(f"  {'would edit' if dry_run else 'edited'} {p.relative_to(ROOT)} ({n} names)")
            if not dry_run:
                p.write_bytes(new.encode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["check", "apply"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = db.connect()
    passed = {}
    for old, new in MOVES.items():
        ok, note = check(conn, old, new)
        print(f"{'PASS' if ok else 'HOLD'} {old} -> {new}: {note}")
        if ok:
            passed[old] = new
    if args.action == "apply":
        print(f"renaming {len(passed)} of {len(MOVES)} series")
        apply(passed, args.dry_run)


if __name__ == "__main__":
    main()
