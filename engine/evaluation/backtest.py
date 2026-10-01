"""Walk-forward backtest.

For each reported period p, as_of is set just before the first ground-truth
row for p became available (the earnings release). The twin is refit from
scratch on data available at as_of, forecasts p, and is scored against the
reported value alongside every baseline.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from engine.evaluation.baselines import baseline_forecasts
from engine.evaluation.metrics import crps_gaussian, crps_samples, gaussian_interval
from engine.estimation.calibration import latest_by_period
from engine.observation import ExternalForecast, GroundTruth, Observation, as_utc, available_as_of
from engine.spec import ResolvedSpec
from engine.twin import Twin

TWIN = "twin"


@dataclass
class BacktestRow:
    period: str
    kpi: str
    model: str
    as_of: datetime
    actual: float
    point: float
    p10: float | None
    p90: float | None
    crps: float
    source_ref: str

    @property
    def covered(self) -> bool | None:
        if self.p10 is None or self.p90 is None:
            return None
        return self.p10 <= self.actual <= self.p90


@dataclass
class Scorecard:
    ticker: str
    spec_hash: str
    rows: list[BacktestRow]

    def table(self) -> list[dict]:
        groups: dict[tuple[str, str], list[BacktestRow]] = defaultdict(list)
        for r in self.rows:
            groups[(r.kpi, r.model)].append(r)
        out = []
        for (kpi, model), rs in sorted(groups.items()):
            err = np.array([r.point - r.actual for r in rs])
            cov = [r.covered for r in rs if r.covered is not None]
            out.append(
                {
                    "kpi": kpi,
                    "model": model,
                    "n": len(rs),
                    "mae": float(np.mean(np.abs(err))),
                    "rmse": float(np.sqrt(np.mean(err**2))),
                    "bias": float(np.mean(err)),
                    "crps": float(np.mean([r.crps for r in rs])),
                    "coverage80": float(np.mean(cov)) if cov else None,
                }
            )
        return out

    def skill(self, baseline: str) -> dict[str, float | None]:
        """CRPS skill vs a baseline on the periods both forecast: 1 - CRPS_twin / CRPS_baseline."""
        out: dict[str, float | None] = {}
        by = {(r.kpi, r.period, r.model): r for r in self.rows}
        for kpi in sorted({r.kpi for r in self.rows}):
            pairs = [
                (by[(kpi, p, TWIN)].crps, by[(kpi, p, baseline)].crps)
                for (k, p, m) in by
                if k == kpi and m == baseline and (kpi, p, TWIN) in by
            ]
            base = sum(b for _, b in pairs)
            out[kpi] = 1 - sum(t for t, _ in pairs) / base if pairs and base > 0 else None
        return out


def walk_forward(
    rspec: ResolvedSpec,
    observations: list[Observation],
    ground_truth: list[GroundTruth],
    external: list[ExternalForecast] | tuple = (),
    test_periods: list[str] | None = None,
    min_train_periods: int = 4,
    n_paths: int = 4000,
    seed: int = 0,
    start_period: str | None = None,
    release_buffer: timedelta = timedelta(hours=1),
) -> Scorecard:
    gt = [g for g in ground_truth if g.entity_id == rspec.ticker]
    release: dict[str, datetime] = {}
    for g in gt:
        t = as_utc(g.available_at)
        release[g.period] = min(release.get(g.period, t), t)
    periods = sorted(release)
    if test_periods is None:
        test_periods = periods[min_train_periods:]

    twin = Twin(rspec, observations, ground_truth, external)
    rows: list[BacktestRow] = []
    for p in test_periods:
        if p not in release:
            continue
        as_of = release[p] - release_buffer
        fitted = twin.fit(as_of, start_period=start_period)
        if p not in fitted.history.periods:
            continue
        fc = fitted.forecast([p], n_paths=n_paths, seed=seed)
        visible_gt = available_as_of(gt, as_of)
        visible_ext = available_as_of(list(external), as_of)
        for kpi in rspec.kpis:
            actual_rows = latest_by_period(gt, rspec.ticker, kpi)
            if p not in actual_rows:
                continue
            actual = actual_rows[p]
            samples = fc.sim.kpis[kpi][:, 0]
            s = fc.summary[kpi][p]
            rows.append(
                BacktestRow(p, kpi, TWIN, as_of, actual.value, s["p50"], s["p10"], s["p90"],
                            crps_samples(samples, actual.value), actual.source_ref)
            )
            for b in baseline_forecasts(rspec.baselines, rspec.period, rspec.ticker, kpi, p, visible_gt, visible_ext,
                                        rspec.excluded_periods):
                if b.sd is not None and math.isfinite(b.sd) and b.sd > 0:
                    lo, hi = gaussian_interval(b.value, b.sd)
                    score = crps_gaussian(b.value, b.sd, actual.value)
                else:
                    lo = hi = None
                    score = abs(b.value - actual.value)
                rows.append(BacktestRow(p, kpi, b.name, as_of, actual.value, b.value, lo, hi, score, b.source_ref))
    return Scorecard(rspec.ticker, rspec.spec_hash(), rows)
