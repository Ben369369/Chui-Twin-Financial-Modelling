"""Ticker in, scored twin out. Builds the spec, ingests data, backtests, writes a portfolio scorecard.

    python scripts/make_twin.py SBUX
    python scripts/make_twin.py SBUX MCD UAL MAR DHI --scorecard docs/portfolio_scorecard.md
    python scripts/make_twin.py --specs specs/cmg.yaml specs/dal.yaml --scorecard docs/portfolio_scorecard.md
    python scripts/make_twin.py CCL --llm                      # an LLM reads the 10-K and refines the spec
    python scripts/make_twin.py MAR --llm --out specs/experiments/llm   # compare with the rules-only twin

Shared series (FRED, BLS, TSA) are fetched once and reused by every twin that maps them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.evaluation.backtest import TWIN, walk_forward  # noqa: E402
from engine.periods import span  # noqa: E402
from engine.spec import load_spec  # noqa: E402
from onboarding.factory import NotCovered, build_spec, write_spec  # noqa: E402
from scripts.ingest import ingest_ground_truth, ingest_signals  # noqa: E402
from storage import db  # noqa: E402

TEST_FROM = "2017Q1"
SCORE_EXCLUDE = set(span("2020Q1", "2021Q4"))  # COVID quarters scored separately


def known_series(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT DISTINCT series FROM observations")}


def score(rspec, conn) -> dict:
    obs = db.load_observations(conn, [s.series for s in rspec.signals])
    gt = db.load_ground_truth(conn, rspec.ticker)
    periods = sorted({g.period for g in gt})
    # Score on the same history the twin is calibrated on: drop COVID for everyone, plus
    # any regime break the spec excludes (e.g. travel through 2022).
    skip = SCORE_EXCLUDE | rspec.excluded_periods
    test = [p for p in periods if p >= TEST_FROM and p not in skip]
    card = walk_forward(rspec, obs, gt, db.load_external(conn, rspec.ticker), test_periods=test, n_paths=2000)
    table = {(r["kpi"], r["model"]): r for r in card.table()}
    out = {"gt_quarters": len(periods), "test_quarters": len(test), "kpis": {}}
    skill_naive, skill_seasonal = card.skill("naive_last"), card.skill("seasonal_naive")
    for kpi in rspec.kpis:
        if (kpi, TWIN) not in table:
            continue
        out["kpis"][kpi] = {
            "n": table[(kpi, TWIN)]["n"],
            "mae_twin": table[(kpi, TWIN)]["mae"],
            "mae_naive": table.get((kpi, "naive_last"), {}).get("mae"),
            "mae_seasonal": table.get((kpi, "seasonal_naive"), {}).get("mae"),
            "skill_naive": skill_naive.get(kpi),
            "skill_seasonal": skill_seasonal.get(kpi),
            "coverage80": table[(kpi, TWIN)]["coverage80"],
        }
    return out


def make(ticker: str, conn, llm: bool = False, out: Path = ROOT / "specs" / "auto") -> tuple[Path, dict]:
    spec, notes = build_spec(ticker, llm=llm)
    path = write_spec(spec, out, notes.get("onboarding"))
    rspec = load_spec(path, ROOT / "templates")
    have = known_series(conn)
    fresh = [s for s in rspec.signals if s.series not in have]
    if fresh:
        import dataclasses
        ingest_signals(dataclasses.replace(rspec, signals=fresh), conn, date(2012, 1, 1), date.today() + timedelta(days=1))
    ingest_ground_truth(rspec, conn, date(2012, 1, 1), reparse=False)
    return path, notes


def fmt(v, spec="+.2f"):
    return "-" if v is None else format(v, spec)


def write_scorecard(results: list[dict], path: Path) -> None:
    lines = [
        "# Portfolio scorecard",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `scripts/make_twin.py`. Walk-forward from {TEST_FROM}, "
        "refit at every earnings release on data available at that moment. COVID quarters (2020Q1-2021Q4), plus any "
        "regime break a spec excludes from calibration (travel: through 2022Q4), are excluded from scoring. "
        "Factory twins use industry-pack defaults with no per-company tuning. Build time (s) is shown when the "
        "twin was built in this run; factory builds took 17-209 s on 2026-10-01, mostly waiting on rate limits. CRPS skill = 1 - CRPS(twin) / CRPS(baseline): positive means the twin is better.",
        "",
        "| Ticker | Industry | Built by | Build s | Signals | Quarters | KPI | MAE twin | MAE naive | MAE seasonal | Skill vs naive | Skill vs seasonal | 80% coverage |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        for kpi, k in r["score"]["kpis"].items():
            lines.append(
                f"| {r['ticker']} | {r['industry']} | {r['built_by']} | {fmt(r['seconds'], '.0f')} | {r['signals']} | "
                f"{r['score']['test_quarters']} | {kpi} | {fmt(k['mae_twin'], '.2f')} | {fmt(k['mae_naive'], '.2f')} | "
                f"{fmt(k['mae_seasonal'], '.2f')} | {fmt(k['skill_naive'])} | {fmt(k['skill_seasonal'])} | "
                f"{fmt(k['coverage80'], '.2f')} |"
            )
    beats = [k for r in results for k in r["score"]["kpis"].values() if (k["skill_naive"] or -1) > 0]
    total = sum(len(r["score"]["kpis"]) for r in results)
    lines += ["", f"Twin beats naive (CRPS) on {len(beats)} of {total} KPI series."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps({
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "test_from": TEST_FROM, "twins": results}, indent=1, default=str), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tickers", nargs="*")
    ap.add_argument("--specs", nargs="*", default=[], help="hand-built specs to score alongside")
    ap.add_argument("--scorecard", default=None)
    ap.add_argument("--llm", action="store_true", help="LLM reads each ticker's 10-K (onboarding/llm.py)")
    ap.add_argument("--out", default="specs/auto", help="where to write specs built from tickers")
    args = ap.parse_args()

    conn = db.connect()
    results = []
    jobs = [("spec", s) for s in args.specs] + [("ticker", t) for t in args.tickers]
    for kind, item in jobs:
        t0 = time.time()
        try:
            if kind == "ticker":
                path, notes = make(item, conn, llm=args.llm, out=ROOT / args.out)
                built_by = "factory+llm" if args.llm else "factory"
                print(f"[{item}] {notes['pack']} (SIC {notes['sic']}), news '{notes['news_query']}', wiki {notes['wiki_article']}")
                if args.llm:
                    o = notes["onboarding"]
                    acc = o["accepted"]
                    print(f"  LLM {o['model']} on 10-K {o['accession']}: +{len(acc['drivers'])} drivers, "
                          f"+{len(acc['kpis'])} KPIs, {len(acc['edges'])} edges, {len(o['rejected'])} rejected "
                          f"({o['input_tokens']:,} in / {o['output_tokens']:,} out tokens)")
            else:
                path = Path(item)
                built_by = ("factory+llm" if path.with_name(f"{path.stem}.onboarding.json").exists()
                            else "factory" if path.parent.name == "auto" else "hand")
            rspec = load_spec(path, ROOT / "templates")
            build_s = time.time() - t0 if kind == "ticker" else None
            sc = score(rspec, conn)
            results.append({"ticker": rspec.ticker, "industry": _industry(path), "built_by": built_by,
                            "seconds": build_s, "signals": len(rspec.signals), "score": sc})
            for kpi, k in sc["kpis"].items():
                print(f"  {kpi:15s} n={k['n']:2d} MAE twin {k['mae_twin']:.2f} naive {fmt(k['mae_naive'], '.2f')} "
                      f"skill vs naive {fmt(k['skill_naive'])} vs seasonal {fmt(k['skill_seasonal'])}")
            print(f"  {'built in %.0fs, ' % build_s if build_s is not None else ''}total {time.time() - t0:.0f}s")
        except NotCovered as e:
            print(f"[{item}] NOT COVERED: {e}")
        except Exception as e:
            print(f"[{item}] FAILED: {type(e).__name__}: {e}")
            traceback.print_exc(limit=2)
    if args.scorecard and results:
        write_scorecard(results, ROOT / args.scorecard)
        print(f"wrote {args.scorecard}")


def _industry(path: Path) -> str:
    import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("industry", "")


if __name__ == "__main__":
    main()
