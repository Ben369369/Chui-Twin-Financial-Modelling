"""v0 latent state estimation: decay-weighted signals fused by precision.

For each signal and period the steps are:
  1. anchor = min(period end, as_of date)
  2. level(a) = exponentially decay-weighted mean of observations whose
     effective date (observed_at + lag_days) is on or before a
  3. feature = transform(level(anchor), level(anchor - 364 days))
  4. z = feature standardized over all periods available at as_of
  5. state = precision-weighted mean of sign * z over signals, with a N(0, 1)
     prior, where precision = c / (1 - c) * 0.5 ** (staleness / half_life)

Only observations with available_at <= as_of are used. See docs/model.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np

from engine.observation import Observation, as_utc, available_as_of
from engine.periods import bounds, period_of, span
from engine.spec import ResolvedSpec, SignalSpec

YEAR_DAYS = 364  # 52 weeks keeps weekday mix aligned for daily series
LOOKBACK_HALF_LIVES = 4.0


@dataclass
class SignalReading:
    series: str
    primitive: str
    period: str
    anchor: date
    feature: float
    z: float | None
    precision: float
    staleness_days: int
    n_obs: int
    source_refs: list[str]


@dataclass
class StateEstimate:
    primitive: str
    period: str
    mean: float
    variance: float
    # series -> additive contribution to mean; contributions sum to mean.
    contributions: dict[str, float] = field(default_factory=dict)


@dataclass
class StateHistory:
    as_of: datetime
    periods: list[str]
    states: dict[tuple[str, str], StateEstimate]
    readings: dict[tuple[str, str], SignalReading]

    @property
    def latest_period(self) -> str:
        return self.periods[-1]

    def get(self, primitive: str, period: str) -> StateEstimate | None:
        return self.states.get((primitive, period))

    def mean(self, primitive: str, period: str) -> float:
        return self.states[(primitive, period)].mean

    def refs_for(self, series: str, period: str) -> list[str]:
        r = self.readings.get((series, period))
        return r.source_refs if r else []


class _Series:
    """Observations of one series, sorted by effective date, as arrays."""

    def __init__(self, obs: list[Observation], lag_days: int):
        obs = sorted(obs, key=lambda o: o.observed_at)
        self.days = np.array([(o.observed_at + timedelta(days=lag_days)).toordinal() for o in obs], dtype=np.int64)
        self.values = np.array([o.value for o in obs], dtype=float)
        self.refs = [o.source_ref for o in obs]

    def level(self, anchor: date, half_life: float) -> tuple[float, int, int, list[str]] | None:
        a = anchor.toordinal()
        lo = a - int(math.ceil(LOOKBACK_HALF_LIVES * half_life))
        i0, i1 = np.searchsorted(self.days, lo, "left"), np.searchsorted(self.days, a, "right")
        if i1 <= i0:
            return None
        age = a - self.days[i0:i1]
        w = 0.5 ** (age / half_life)
        value = float(np.dot(w, self.values[i0:i1]) / w.sum())
        refs = sorted(set(self.refs[i0:i1]))
        return value, int(age.min()), i1 - i0, refs


def _feature(series: _Series, sig: SignalSpec, anchor: date):
    now = series.level(anchor, sig.half_life_days)
    if now is None:
        return None
    value, staleness, n, refs = now
    if sig.transform == "level":
        return value, staleness, n, refs
    past = series.level(anchor - timedelta(days=YEAR_DAYS), sig.half_life_days)
    if past is None:
        return None
    if sig.transform == "yoy_diff":
        return value - past[0], staleness, n, sorted(set(refs) | set(past[3]))
    if value <= 0 or past[0] <= 0:
        return None
    return math.log(value / past[0]), staleness, n, sorted(set(refs) | set(past[3]))


def _matches(o: Observation, sig: SignalSpec, ticker: str) -> bool:
    if o.series != sig.series:
        return False
    if sig.entity_id is not None:
        return o.entity_id == sig.entity_id
    return o.entity_id in (ticker, "macro")


def estimate_states(
    rspec: ResolvedSpec,
    observations: list[Observation],
    as_of: datetime,
    start_period: str,
    min_history: int = 6,
) -> StateHistory:
    as_of = as_utc(as_of)
    obs = available_as_of(observations, as_of)
    end_period = period_of(as_of.date(), rspec.period)
    periods = span(start_period, end_period)
    anchors = {p: min(bounds(p)[1], as_of.date()) for p in periods}

    readings: dict[tuple[str, str], SignalReading] = {}
    for sig in rspec.signals:
        series = _Series([o for o in obs if _matches(o, sig, rspec.ticker)], sig.lag_days)
        if len(series.days) == 0:
            continue
        raw: dict[str, tuple] = {}
        for p in periods:
            f = _feature(series, sig, anchors[p])
            if f is not None:
                raw[p] = f
        if len(raw) < min_history:
            continue
        feats = np.array([v[0] for v in raw.values()])
        mu, sd = float(feats.mean()), float(feats.std(ddof=1))
        if not np.isfinite(sd) or sd <= 1e-12:
            continue
        base_precision = sig.confidence / (1.0 - sig.confidence)
        for p, (value, staleness, n, refs) in raw.items():
            readings[(sig.series, p)] = SignalReading(
                series=sig.series,
                primitive=sig.primitive,
                period=p,
                anchor=anchors[p],
                feature=value,
                z=(value - mu) / sd,
                precision=base_precision * 0.5 ** (staleness / sig.half_life_days),
                staleness_days=staleness,
                n_obs=n,
                source_refs=refs,
            )

    signs = {s.series: s.sign for s in rspec.signals}
    states: dict[tuple[str, str], StateEstimate] = {}
    for p in periods:
        for prim in rspec.primitive_names:
            rs = [r for (s, q), r in readings.items() if q == p and r.primitive == prim]
            total = 1.0 + sum(r.precision for r in rs)  # N(0, 1) prior has precision 1
            contrib = {r.series: r.precision * signs[r.series] * r.z / total for r in rs}
            states[(prim, p)] = StateEstimate(
                primitive=prim,
                period=p,
                mean=float(sum(contrib.values())),
                variance=1.0 / total,
                contributions=contrib,
            )
    return StateHistory(as_of=as_of, periods=periods, states=states, readings=readings)
