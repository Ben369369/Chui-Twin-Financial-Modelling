"""Read-only API over the twins. Every number it returns carries its sources.

    uvicorn api.main:app --reload

GET  /twins                               all twins (hand-built and factory-built)
GET  /twins/{ticker}                      spec summary, KPI models, latest states
GET  /twins/{ticker}/forecast             distribution, waterfall, expectation gaps
       ?shock=sentiment:2026Q4:-2:2       (repeatable) scenario shocks, primitive:period:size_sd[:half_life]
       &paths=10000&as_of=2026-10-01T00:00:00+00:00
GET  /twins/{ticker}/history              reported KPIs and estimated states by period
GET  /scorecard                           docs/portfolio_scorecard.md as text
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from adapters.http import data_root
from engine.estimation.calibration import latest_by_period
from engine.simulation.montecarlo import Shock
from engine.spec import ResolvedSpec, load_spec
from engine.twin import Twin
from storage import db

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="Chui Twin", version="0.2")


def spec_paths() -> dict[str, Path]:
    paths = sorted((ROOT / "specs").glob("*.yaml")) + sorted((ROOT / "specs" / "auto").glob("*.yaml"))
    out: dict[str, Path] = {}
    for p in paths:  # hand-built specs win over factory specs for the same ticker
        out.setdefault(load_spec(p, ROOT / "templates").ticker, p)
    return out


def _twin(ticker: str) -> tuple[ResolvedSpec, Twin, str]:
    paths = spec_paths()
    if ticker not in paths:
        raise HTTPException(404, f"no twin for {ticker}; known: {sorted(paths)}")
    # Cache until the spec or the database changes, so refreshed data shows without a restart.
    db_file = data_root() / "chui.sqlite"
    stamp = (paths[ticker].stat().st_mtime, db_file.stat().st_mtime if db_file.exists() else 0.0)
    return _load_twin(ticker, str(paths[ticker]), stamp)


@lru_cache(maxsize=64)
def _load_twin(ticker: str, spec_path: str, stamp: tuple[float, float]) -> tuple[ResolvedSpec, Twin, str]:
    paths = {ticker: Path(spec_path)}
    rspec = load_spec(paths[ticker], ROOT / "templates")
    conn = db.connect()
    twin = Twin(rspec, db.load_observations(conn, [s.series for s in rspec.signals]),
                db.load_ground_truth(conn, ticker), db.load_external(conn, ticker))
    built_by = "factory" if paths[ticker].parent.name == "auto" else "hand"
    return rspec, twin, built_by


def _as_of(text: str | None) -> datetime:
    return datetime.fromisoformat(text) if text else datetime.now(timezone.utc)


def _shock(text: str) -> Shock:
    parts = text.split(":")
    if len(parts) < 3:
        raise HTTPException(400, "shock must be primitive:period:size_sd[:half_life_periods]")
    return Shock(parts[0], parts[1], float(parts[2]), float(parts[3]) if len(parts) > 3 else 1.0, label=text)


@app.get("/twins")
def list_twins() -> list[dict]:
    out = []
    for ticker in spec_paths():
        rspec, _, built_by = _twin(ticker)
        out.append({"ticker": ticker, "name": rspec.name, "template": rspec.template, "built_by": built_by,
                    "kpis": list(rspec.kpis), "signals": [s.series for s in rspec.signals]})
    return out


@app.get("/twins/{ticker}")
def twin_detail(ticker: str, as_of: str | None = None) -> dict:
    rspec, twin, built_by = _twin(ticker.upper())
    fitted = twin.fit(_as_of(as_of))
    last = fitted.history.latest_period
    return {
        "ticker": rspec.ticker, "name": rspec.name, "built_by": built_by, "spec_hash": rspec.spec_hash(),
        "as_of": fitted.as_of.isoformat(), "notes": rspec.notes,
        "signals": [s.model_dump() for s in rspec.signals],
        "edges": [e.model_dump(by_alias=True) for e in rspec.primitive_edges + rspec.kpi_edges],
        "kpi_models": {k: {"target": m.target, "parents": m.parents, "lags": m.lags, "coef_mean": m.coef_mean.tolist(),
                           "sigma": m.sigma, "n_obs": m.n_obs} for k, m in fitted.models.items()},
        "states": {p: {"mean": fitted.history.get(p, last).mean, "variance": fitted.history.get(p, last).variance,
                       "contributions": fitted.history.get(p, last).contributions} for p in rspec.primitive_names},
        "states_period": last,
    }


@app.get("/twins/{ticker}/forecast")
def forecast(ticker: str, shock: list[str] = Query(default=[]), paths: int = 10_000, as_of: str | None = None) -> dict:
    rspec, twin, _ = _twin(ticker.upper())
    fitted = twin.fit(_as_of(as_of))
    shocks = [_shock(s) for s in shock]
    base = fitted.forecast(n_paths=paths)
    record = base.to_record()
    if shocks:
        scen = fitted.forecast(periods=list(base.sim.periods), n_paths=paths, shocks=shocks)
        record["scenario"] = {"shocks": shock, "forecast": scen.summary,
                              "waterfall": scen.to_record()["waterfall"],
                              "delta_mean": {k: {p: scen.summary[k][p]["mean"] - base.summary[k][p]["mean"]
                                                 for p in base.summary[k]} for k in base.summary}}
    return record


@app.get("/twins/{ticker}/history")
def history(ticker: str, as_of: str | None = None) -> dict:
    rspec, twin, _ = _twin(ticker.upper())
    fitted = twin.fit(_as_of(as_of))
    reported = {k: {p: {"value": g.value, "source_ref": g.source_ref} for p, g in
                    latest_by_period(fitted.ground_truth, rspec.ticker, k).items()} for k in rspec.kpis}
    states = {prim: {p: fitted.history.get(prim, p).mean for p in fitted.history.periods}
              for prim in rspec.primitive_names}
    return {"ticker": rspec.ticker, "reported": reported, "states": states}


@app.get("/scorecard")
def scorecard() -> dict:
    path = ROOT / "docs" / "portfolio_scorecard.json"
    if not path.exists():
        raise HTTPException(404, "run scripts/make_twin.py --specs ... --scorecard docs/portfolio_scorecard.md first")
    return json.loads(path.read_text(encoding="utf-8"))
