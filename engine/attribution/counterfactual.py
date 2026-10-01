"""Leave-one-signal-out counterfactuals: Delta_i = Y(all signals) - Y(without signal i).

Unlike the waterfall, this refits everything (states and KPI calibration)
without the signal, so it also captures how a signal changes the fitted edges.
Common random numbers (same seed) keep the differences low-noise.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime

from engine.observation import GroundTruth, Observation
from engine.spec import ResolvedSpec
from engine.twin import Twin


@dataclass
class SignalImpact:
    series: str
    primitive: str
    kpi: str
    period: str
    delta_mean: float
    delta_p50: float


def leave_one_signal_out(
    rspec: ResolvedSpec,
    observations: list[Observation],
    ground_truth: list[GroundTruth],
    as_of: datetime,
    period: str,
    n_paths: int = 4000,
    seed: int = 0,
    start_period: str | None = None,
) -> list[SignalImpact]:
    def run(spec: ResolvedSpec):
        fitted = Twin(spec, observations, ground_truth).fit(as_of, start_period=start_period)
        return fitted.forecast([period], n_paths=n_paths, seed=seed).sim.summary()

    full = run(rspec)
    impacts = []
    for sig in rspec.signals:
        reduced = dataclasses.replace(rspec, signals=[s for s in rspec.signals if s.series != sig.series])
        without = run(reduced)
        for kpi in rspec.kpis:
            a, b = full[kpi][period], without[kpi][period]
            impacts.append(
                SignalImpact(sig.series, sig.primitive, kpi, period, a["mean"] - b["mean"], a["p50"] - b["p50"])
            )
    return impacts
