"""Synthetic twin data with a known truth, for any resolved spec.

Latent primitives follow AR(1) per period. Each signal is observed weekly as
sign * state + noise (use transform: level in the spec). Modeled KPIs are
linear in their parent states with the edge prior means as true coefficients.
Ground truth for period p is released 30 days after the period ends.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import numpy as np

from engine.observation import GroundTruth, Observation
from engine.periods import bounds, span
from engine.spec import ResolvedSpec

KPI_SCALE = 3.0
KPI_NOISE = 0.5
RELEASE_LAG_DAYS = 30


def generate(rspec: ResolvedSpec, first: str, last: str, seed: int = 7, signal_noise: float = 0.3):
    rng = np.random.default_rng(seed)
    periods = span(first, last)
    rho = {p.name: p.persistence for p in rspec.primitives}
    truth = {p: np.zeros(len(periods)) for p in rspec.primitive_names}
    for p in rspec.primitive_names:
        x = 0.0
        for i in range(len(periods)):
            x = rho[p] * x + np.sqrt(1 - rho[p] ** 2) * rng.standard_normal()
            truth[p][i] = x

    obs: list[Observation] = []
    for sig in rspec.signals:
        for i, per in enumerate(periods):
            start, end = bounds(per)
            d = start
            while d <= end:
                v = sig.sign * truth[sig.primitive][i] + signal_noise * rng.standard_normal()
                obs.append(Observation(rspec.ticker, "synthetic", sig.series, d,
                                       datetime.combine(d + timedelta(days=1), time(0), timezone.utc),
                                       float(v), "z", None, f"synthetic:{sig.series}:{d}"))
                d += timedelta(days=7)

    gt: list[GroundTruth] = []
    values: dict[str, list[float]] = {}
    for k in rspec.kpi_order():
        values[k] = []
        for i, per in enumerate(periods):
            if k in rspec.formulas:
                v = float(rspec.formulas[k].evaluate({n: values[n][i] for n in rspec.formulas[k].names}))
            else:
                v = KPI_NOISE * rng.standard_normal()
                for e in rspec.kpi_edges:
                    if e.target == k:
                        v += KPI_SCALE * e.prior_mean * truth[e.source][i]
            values[k].append(v)
            release = datetime.combine(bounds(per)[1] + timedelta(days=RELEASE_LAG_DAYS), time(21), timezone.utc)
            gt.append(GroundTruth(rspec.ticker, per, k, v, release, f"synthetic:{k}:{per}"))
    return obs, gt, truth, periods
