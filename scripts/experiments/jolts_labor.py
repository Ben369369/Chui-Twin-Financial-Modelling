"""Labor proxy experiment: do JOLTS hiring-difficulty series improve the CMG and DAL backtests?

    python scripts/experiments/jolts_labor.py      # ~10 minutes; results recorded in docs/experiments.md

Ingests JOLTS quits and job-openings rates for each twin's industry, writes spec variants
(base, +quits, +openings, +both) to data/experiments/jolts/, and runs the walk-forward backtest
on each with the scorecard's exclusions. The specs in specs/ are not changed.
"""

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "experiments" / "jolts"  # gitignored
sys.path.insert(0, str(ROOT))

from adapters import adapter_for  # noqa: E402
from storage import db  # noqa: E402

# (quits rate, job openings rate) for the twin's industry
JOLTS = {"cmg": ("fred:JTS7200QUR", "fred:JTS7200JOR"), "dal": ("fred:JTU480099QUR", "fred:JTU480099JOR")}
EXCLUDE = {"cmg": "2020Q1:2021Q4", "dal": "2020Q1:2022Q4"}


def labor_signal(series: str) -> dict:
    # Rates in percent: the year-over-year difference removes seasonality (the transport series is not SA).
    return {"series": series, "primitive": "labor", "sign": 1, "confidence": 0.4, "half_life_days": 60,
            "transform": "yoy_diff"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    conn = db.connect()
    for s in [x for pair in JOLTS.values() for x in pair]:
        a = adapter_for(s)
        snaps = a.fetch(a.params_for_series(s), date(2012, 1, 1), date.today() + timedelta(days=1))
        obs = [o for o in a.normalize(snaps) if o.series == s]
        db.save_snapshots(conn, snaps)
        db.save_observations(conn, obs)
        print("ingested", s, len(obs))

    for twin, (quits, openings) in JOLTS.items():
        spec = yaml.safe_load((ROOT / "specs" / f"{twin}.yaml").read_text(encoding="utf-8"))
        variants = {"base": [], "quits": [quits], "openings": [openings], "both": [quits, openings]}
        for name, extra in variants.items():
            path = OUT / f"{twin}_{name}.yaml"
            path.write_text(yaml.safe_dump(dict(spec, signals=spec["signals"] + [labor_signal(s) for s in extra]),
                                           sort_keys=False), encoding="utf-8")
            r = subprocess.run([sys.executable, str(ROOT / "scripts" / "backtest.py"), str(path), "--from", "2017Q1",
                                "--exclude", EXCLUDE[twin], "--json", str(OUT / f"{twin}_{name}.json")],
                               capture_output=True, text=True, cwd=ROOT)
            print(f"===== {twin} {name}\n{r.stdout}{r.stderr[-800:]}")


if __name__ == "__main__":
    main()
