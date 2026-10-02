"""Scenarios defined on data series instead of hidden states.

A move of k standard deviations in one series (for example a market index) shifts the state it
informs by k times that series' weight in the latest state estimate:

    weight_s = precision_s / (1 + sum of precisions) = precision_s * state variance

which is exactly how much a one-sd surprise in that series would move the estimate. Running the
same series move through every twin that maps it gives a portfolio-wide shock, propagated by each
twin's own calibrated graph.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.estimation.weighted import StateHistory
from engine.simulation.montecarlo import Shock
from engine.spec import ResolvedSpec


@dataclass(frozen=True)
class SeriesShock:
    primitive: str
    weight: float  # state sd moved per sd of the series
    size: float  # resulting state shock, in sd
    reading_period: str  # period whose estimate the weight comes from
    transform: str  # the series feature: yoy_log, yoy_diff or level
    feature_sd: float  # one sd of that feature in its natural units, over the twin's history

    @property
    def natural_move(self) -> float:
        """The series move in natural units (yoy_log as percent), so "-2 sd" can be read as a size."""
        move = self.size_sd * self.feature_sd
        return 100.0 * move if self.transform == "yoy_log" else move

    @property
    def size_sd(self) -> float:
        return self.size / self.weight if self.weight else 0.0


def series_shock(rspec: ResolvedSpec, history: StateHistory, series: str, size_sd: float) -> SeriesShock | None:
    """Translate a series move into a state shock, or None if this twin does not use the series."""
    sig = next((s for s in rspec.signals if s.series == series), None)
    if sig is None:
        return None
    for period in reversed(history.periods):  # latest period where the series has a reading
        reading = history.readings.get((series, period))
        est = history.get(sig.primitive, period)
        if reading is not None and est is not None:
            weight = reading.precision * est.variance
            feats = [r.feature for (sr, _), r in history.readings.items() if sr == series]
            mean = sum(feats) / len(feats)
            sd = (sum((f - mean) ** 2 for f in feats) / max(len(feats) - 1, 1)) ** 0.5
            return SeriesShock(sig.primitive, weight, sig.sign * weight * size_sd, period, sig.transform, sd)
    return None


def as_shocks(s: SeriesShock | None, period: str, half_life: float, label: str) -> list[Shock]:
    return [] if s is None else [Shock(s.primitive, period, s.size, half_life, label=label)]
