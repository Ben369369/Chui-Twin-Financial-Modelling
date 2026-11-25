"""Seal every twin's next forecast shortly before the company reports, so the live record grows by itself.

    python scripts/auto_seal.py              # seal each twin whose window is open
    python scripts/auto_seal.py --dry-run    # print the calendar, seal nothing

No earnings calendar is needed. The expected release of a period is estimated from the company's own
history in the ground-truth table: the dates the same period was reported in each of the last two years,
moved forward by whole weeks (companies report on the same weekday), taking the earlier one. A twin is
sealed once per period, on the first run inside the window that opens --lead-days before that date.
A seal already made inside the window (by hand or by this script) counts.

The estimate does not have to be right for the test to stay honest: resolve_sealed.py rejects any
outcome that was public before the seal. If a company reports earlier than expected, that seal is
marked invalid and the next period is sealed as usual.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.periods import periods_per_year, shift  # noqa: E402
from engine.spec import load_spec  # noqa: E402
from engine.twin import Twin  # noqa: E402
from scripts.forecast import seal_and_stamp  # noqa: E402
from storage import db  # noqa: E402

SEALED = ROOT / "forecasts" / "sealed"


def release_dates(truth) -> dict[str, date]:
    """Period -> first date any KPI of that period became public (the earnings release)."""
    out: dict[str, date] = {}
    for g in truth:
        d = g.available_at.date()
        out[g.period] = min(out.get(g.period, d), d)
    return out


def expected_release(released: dict[str, date], period: str, freq: str) -> date | None:
    n = periods_per_year(freq)
    guesses = []
    for years in (1, 2):
        past = released.get(shift(period, -n * years))
        if past is not None:
            guesses.append(past + timedelta(weeks=52 * years))
    return min(guesses) if guesses else None


def already_sealed(ticker: str, period: str, since: date, sealed_dir: Path = SEALED) -> Path | None:
    """A sealed file for this ticker, made on or after `since`, whose forecast covers `period`."""
    for path in sorted(sealed_dir.glob(f"{ticker}_*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        made = datetime.fromisoformat(rec["sealed_at"]).date()
        if made >= since and any(period in by_p for by_p in rec["forecast"].values()):
            return path
    return None


def plan(rspec, truth, today: date, lead_days: int, sealed_dir: Path = SEALED) -> dict:
    """What to do for one twin today: seal, wait, or skip, and why."""
    released = release_dates([g for g in truth if g.kpi in rspec.kpis])
    if not released:
        return {"action": "skip", "why": "no reported history"}
    period = shift(max(released), 1)
    due = expected_release(released, period, rspec.period)
    row = {"period": period, "expected": due}
    if due is None:
        return row | {"action": "skip", "why": "no release history for this period a year earlier"}
    opens = due - timedelta(days=lead_days)
    if today < opens:
        return row | {"action": "wait", "why": f"window opens {opens}"}
    if today >= due:
        return row | {"action": "skip", "why": "expected release has passed; not reported in data yet"}
    if (prior := already_sealed(rspec.ticker, period, opens, sealed_dir)) is not None:
        return row | {"action": "done", "why": f"sealed {prior.name}"}
    return row | {"action": "seal", "why": f"window open ({opens} to {due})"}


def specs() -> list:
    """Hand-built specs win over auto specs for the same ticker."""
    out, seen = [], set()
    for p in sorted((ROOT / "specs").glob("*.yaml")) + sorted((ROOT / "specs" / "auto").glob("*.yaml")):
        rspec = load_spec(p, ROOT / "templates")
        if rspec.ticker not in seen:
            seen.add(rspec.ticker)
            out.append(rspec)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lead-days", type=int, default=10, help="seal this many days before the expected release")
    ap.add_argument("--paths", type=int, default=10_000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = db.connect()
    today = datetime.now(timezone.utc).date()
    failures = []
    for rspec in specs():
        truth = db.load_ground_truth(conn, rspec.ticker)
        p = plan(rspec, truth, today, args.lead_days)
        print(f"  {rspec.ticker:5s} {p.get('period', '-'):7s} expected {p.get('expected') or '-'!s:10s} "
              f"{p['action']:5s} {p['why']}")
        if p["action"] != "seal" or args.dry_run:
            continue
        try:
            twin = Twin(rspec, db.load_observations(conn, [s.series for s in rspec.signals]), truth,
                        db.load_external(conn, rspec.ticker))
            fc = twin.fit(datetime.now(timezone.utc)).forecast(n_paths=args.paths)
            if p["period"] not in next(iter(fc.summary.values())):
                raise RuntimeError(f"forecast does not cover {p['period']}")
            seal_and_stamp(fc.to_record())
        except Exception as e:
            failures.append(rspec.ticker)
            print(f"  FAIL {rspec.ticker}: {type(e).__name__}: {e}")
            traceback.print_exc(limit=1)
    if failures:
        print(f"{len(failures)} seal failures: {failures}")
        sys.exit(1)


if __name__ == "__main__":
    main()
