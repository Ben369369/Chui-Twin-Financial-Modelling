"""Baselines every twin is scored against.

Built-in baselines use only ground truth available at as_of. Their spread is
the RMS of their own past errors, so they get a fair probabilistic score.
External baselines (guidance, consensus) are point forecasts supplied as
ExternalForecast rows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from engine.estimation.calibration import latest_by_period
from engine.observation import ExternalForecast, GroundTruth
from engine.periods import periods_per_year, shift

MIN_ERRORS_FOR_SPREAD = 3


@dataclass
class BaselineForecast:
    name: str
    value: float
    sd: float | None
    source_ref: str


def _lagged(values: dict[str, float], period: str, lag: int) -> float | None:
    return values.get(shift(period, -lag))


def _builtin(name: str, lag: int, rows: dict[str, GroundTruth], period: str,
             exclude: set[str]) -> BaselineForecast | None:
    values = {p: r.value for p, r in rows.items()}
    point = _lagged(values, period, lag)
    if point is None:
        return None
    # Spread from past errors, skipping the periods the twin is not calibrated on,
    # so baseline and twin intervals are sized on the same history.
    errors = [values[p] - v for p in values
              if (v := _lagged(values, p, lag)) is not None and p not in exclude and shift(p, -lag) not in exclude]
    sd = math.sqrt(sum(e * e for e in errors) / len(errors)) if len(errors) >= MIN_ERRORS_FOR_SPREAD else None
    return BaselineForecast(name, point, sd, rows[shift(period, -lag)].source_ref)


def baseline_forecasts(
    names: list[str],
    freq: str,
    entity_id: str,
    kpi: str,
    period: str,
    ground_truth: list[GroundTruth],
    external: list[ExternalForecast],
    exclude: set[str] | frozenset = frozenset(),
) -> list[BaselineForecast]:
    """All inputs must already be cut to as_of."""
    rows = latest_by_period(ground_truth, entity_id, kpi)
    out: list[BaselineForecast] = []
    for name in names:
        if name == "naive_last":
            b = _builtin(name, 1, rows, period, set(exclude))
        elif name == "seasonal_naive":
            b = _builtin(name, periods_per_year(freq), rows, period, set(exclude))
        else:
            cands = sorted(
                (e for e in external if e.source == name and e.entity_id == entity_id and e.kpi == kpi and e.period == period),
                key=lambda e: e.available_at,
            )
            b = BaselineForecast(name, cands[-1].value, None, cands[-1].source_ref) if cands else None
        if b is not None:
            out.append(b)
    return out
