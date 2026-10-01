"""Current forecast for one twin: distribution, driver waterfall, optional scenario and seal.

    python scripts/forecast.py specs/cmg.yaml
    python scripts/forecast.py specs/cmg.yaml --shock sentiment:2026Q4:-2:2 --shock input_cost:2026Q4:1.5
    python scripts/forecast.py specs/cmg.yaml --seal      # writes forecasts/sealed/<file>.json and prints its SHA-256

A shock is primitive:period:size_in_sd[:half_life_periods].
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.sealing import seal  # noqa: E402
from engine.simulation.montecarlo import Shock  # noqa: E402
from engine.spec import load_spec  # noqa: E402
from engine.twin import Twin  # noqa: E402
from storage import db  # noqa: E402


def parse_shock(text: str) -> Shock:
    parts = text.split(":")
    return Shock(parts[0], parts[1], float(parts[2]), float(parts[3]) if len(parts) > 3 else 1.0, label=text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--as-of", default=None, help="ISO datetime, default now (UTC)")
    ap.add_argument("--paths", type=int, default=10_000)
    ap.add_argument("--shock", action="append", default=[])
    ap.add_argument("--seal", action="store_true")
    args = ap.parse_args()

    rspec = load_spec(args.spec, ROOT / "templates")
    conn = db.connect()
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(timezone.utc)
    twin = Twin(rspec, db.load_observations(conn, [s.series for s in rspec.signals]),
                db.load_ground_truth(conn, rspec.ticker), db.load_external(conn, rspec.ticker))
    fitted = twin.fit(as_of)
    shocks = [parse_shock(s) for s in args.shock]
    fc = fitted.forecast(n_paths=args.paths, shocks=shocks)

    print(f"{rspec.ticker} as of {fitted.as_of:%Y-%m-%d %H:%M} UTC, {args.paths} paths, spec {rspec.spec_hash()[:12]}")
    print("\nStates (standardized; 0 = historical average):")
    for p in fitted.history.periods[-3:]:
        cells = [f"{prim} {fitted.history.get(prim, p).mean:+.2f}" for prim in rspec.primitive_names]
        print(f"  {p}: " + "  ".join(cells))
    print("\nKPI models:")
    for k, m in fitted.models.items():
        terms = ", ".join(f"{pr} {c:+.2f}" for pr, c in zip(m.parents, m.coef_mean[1:]))
        lag = f", lag {m.lag_coef:+.2f}" if m.has_lag else ""
        print(f"  {k:14s} n={m.n_obs:2d} sigma={m.sigma:5.2f}  {terms}{lag}")
    print("\nForecast:")
    for k, by_p in fc.summary.items():
        for p, s in by_p.items():
            print(f"  {k:14s} {p}  p10 {s['p10']:7.2f}  p50 {s['p50']:7.2f}  p90 {s['p90']:7.2f}")
    for g in fc.gaps:
        print(f"  gap vs {g.source} {g.kpi} {g.period}: expectation {g.expectation:.2f}, "
              f"E[twin]-exp {g.gap_mean:+.2f}, P(twin > exp) {g.prob_above:.0%}")

    first = next(iter(fc.waterfall))
    print(f"\nDriver waterfall, {first} (expected value by driver and signal):")
    for k, rows in fc.waterfall[first].items():
        agg: dict[tuple[str, str | None], float] = defaultdict(float)
        for c in rows:
            agg[(c.driver, c.signal)] += c.value
        print(f"  {k}: total {sum(agg.values()):+.2f}")
        for (drv, sig), v in sorted(agg.items(), key=lambda kv: -abs(kv[1])):
            print(f"      {v:+7.2f}  {drv}{'  <- ' + sig if sig else ''}")

    if args.seal:
        path, digest = seal(fc.to_record(), ROOT / "forecasts" / "sealed")
        print(f"\nSealed {path.relative_to(ROOT)}\nsha256 {digest}\n"
              "Publish this hash somewhere timestamped (a pushed commit, a message to your mentor) before the outcome.")


if __name__ == "__main__":
    main()
