"""Does the twin know more than the published expectation (guidance, consensus)?

Two tests per KPI and expectation, on the same walk-forward quarters:
  1. Direction: does the twin call beat or miss?
  2. Accuracy: is the twin's forecast closer to the actual than the expectation? Uses the size of each quarter's
     CRPS gain (a point forecast's CRPS is its absolute error), so it has more power than beat/miss.

For every scored quarter where an expectation (guidance, consensus) was public before the release, compare the
sign of (twin median - expectation) with the sign of (actual - expectation). Report the hit rate next to the best
constant rule ("always beat" or "always miss"), because companies that guide low make "always beat" look skilled.

    python scripts/reports/surprise_direction.py                    # specs/cmg.yaml specs/dal.yaml -> docs/surprise_direction.md
    python scripts/reports/surprise_direction.py specs/dal.yaml --out -
"""

from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from engine.evaluation.backtest import TWIN, walk_forward  # noqa: E402
from engine.spec import load_spec  # noqa: E402
from scripts.make_twin import SCORE_EXCLUDE, TEST_FROM  # noqa: E402
from storage import db  # noqa: E402


def p_at_least(hits: int, n: int) -> float:
    """One-sided binomial p-value: chance of >= hits correct calls out of n by coin flip."""
    return sum(math.comb(n, k) for k in range(hits, n + 1)) / 2 ** n


def p_sign_flip(gains: list[float]) -> float:
    """Exact one-sided paired permutation test: the share of the 2^n sign flips whose mean gain is at least the
    observed one. Under "the twin is no better than the expectation", each quarter's gain is equally likely +/-."""
    n, observed = len(gains), sum(gains)
    count = 0
    for mask in range(1 << n):
        total = sum(-g if mask >> i & 1 else g for i, g in enumerate(gains))
        count += total >= observed - 1e-12
    return count / (1 << n)


def direction_table(rspec, conn, n_paths: int = 4000) -> list[dict]:
    obs = db.load_observations(conn, [s.series for s in rspec.signals])
    gt = db.load_ground_truth(conn, rspec.ticker)
    ext = db.load_external(conn, rspec.ticker)
    skip = SCORE_EXCLUDE | rspec.excluded_periods
    test = [p for p in sorted({g.period for g in gt}) if p >= TEST_FROM and p not in skip]
    card = walk_forward(rspec, obs, gt, ext, test_periods=test, n_paths=n_paths)

    by: dict[tuple[str, str], dict] = defaultdict(dict)
    for r in card.rows:
        by[(r.kpi, r.period)][r.model] = r
    out = []
    for source in sorted({e.source for e in ext}):
        for kpi in sorted({k for k, _ in by}):
            both = [(p, m) for (k, p), m in sorted(by.items()) if k == kpi and source in m and TWIN in m]
            gains = [m[source].crps - m[TWIN].crps for _, m in both]  # > 0: the twin was closer
            pairs = [(m[TWIN].point - m[source].point, m[TWIN].actual - m[source].point, p) for p, m in both]
            pairs = [x for x in pairs if x[0] != 0 and x[1] != 0]  # an exact tie has no direction
            if not pairs:
                continue
            n = len(pairs)
            hits = sum((call > 0) == (outcome > 0) for call, outcome, _ in pairs)
            beat = sum(outcome > 0 for _, outcome, _ in pairs)
            out.append({"ticker": rspec.ticker, "kpi": kpi, "vs": source, "n": n, "hits": hits,
                        "beat": beat, "best_constant": max(beat, n - beat), "p": p_at_least(hits, n),
                        "first": pairs[0][2], "last": pairs[-1][2],
                        "acc_n": len(gains), "closer": sum(g > 0 for g in gains),
                        "p_closer": p_at_least(sum(g > 0 for g in gains), len(gains)),
                        "mean_gain": sum(gains) / len(gains), "p_perm": p_sign_flip(gains)})
    return out


def render(rows: list[dict]) -> str:
    lines = [
        "# Surprise direction: does the twin call beat or miss?",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `scripts/reports/surprise_direction.py`. "
        f"Walk-forward from {TEST_FROM} with the scorecard's exclusions; each forecast uses only data public an hour "
        "before the release, and each expectation only if it was public before that moment. A call is the sign of "
        "(twin median - expectation); the outcome is the sign of (actual - expectation). The best constant rule is "
        "\"always beat\" or \"always miss\", whichever scored more: a twin with no information scores about that. "
        "p is the one-sided binomial chance of at least that many hits by coin flip.",
        "",
        "| Twin | KPI | Against | Quarters | Twin hits | Hit rate | Actual beat | Best constant rule | p (vs coin) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['ticker']} | {r['kpi']} | {r['vs']} | {r['n']} ({r['first']}–{r['last']}) | {r['hits']} | "
                     f"{r['hits'] / r['n']:.0%} | {r['beat']} | {r['best_constant'] / r['n']:.0%} | {r['p']:.2f} |")
    lines += [
        "",
        "Read a row as evidence of an information edge only if the hit rate clears the best constant rule, not just "
        "50%, and p is small. With 6–18 quarters per row, none of these is conclusive.",
        "",
        "## Accuracy: is the twin closer to the actual than the expectation?",
        "",
        "Same quarters. Gain = CRPS(expectation) - CRPS(twin) per quarter; a point forecast's CRPS is its absolute "
        "error. Sign test: how often the twin was closer. Permutation p: exact one-sided paired test on the mean gain "
        "(all 2^n sign flips). This uses the size of each quarter's gain, so it has more power than beat/miss, but it "
        "answers a different question: closer than the expectation, not the direction of the surprise.",
        "",
        "| Twin | KPI | Against | Quarters | Twin closer | Sign test p | Mean CRPS gain | Permutation p |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(f"| {r['ticker']} | {r['kpi']} | {r['vs']} | {r['acc_n']} | {r['closer']} of {r['acc_n']} | "
                     f"{r['p_closer']:.3f} | {r['mean_gain']:+.2f} | {r['p_perm']:.3f} |")
    lines += [
        "",
        "Caveats: a company that guides low (Chipotle beat its guide in most quarters) can be beaten partly by "
        "correcting that bias; several tests on 6–18 quarters; the hand-built twins' structure was chosen on this "
        "backtest. None of this is a test against what the price already reflects.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("specs", nargs="*", default=["specs/cmg.yaml", "specs/dal.yaml"])
    ap.add_argument("--out", default="docs/surprise_direction.md", help='"-" prints to stdout')
    args = ap.parse_args()
    conn = db.connect()
    rows = [r for s in args.specs for r in direction_table(load_spec(ROOT / s, ROOT / "templates"), conn)]
    text = render(rows)
    if args.out == "-":
        print(text)
    else:
        (ROOT / args.out).write_text(text, encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()
