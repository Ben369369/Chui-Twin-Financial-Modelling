"""Driver waterfall: decompose a KPI's expected value into signal-level terms.

For a modeled KPI at period t:
    E[y_t] = a + sum_j b_j * E[x_j,t]
and E[x_j,t] = rho_j^k * sum_s contribution_s + shock deltas, where k is the
number of periods past the last estimated period. A lag term phi * y[t-1] is
its own driver ("<kpi>[t-1]") when y[t-1] is reported; otherwise the previous
period's drivers carry forward scaled by phi. Each term keeps the source refs
of the observations behind it. Formula KPIs are linearized at the
component means (exact for linear formulas such as sums).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.estimation.calibration import KPIModel
from engine.estimation.weighted import StateHistory
from engine.observation import GroundTruth
from engine.periods import diff, shift
from engine.simulation.montecarlo import Shock, lag_is_gap, shock_deltas
from engine.spec import ResolvedSpec

BASELINE = "baseline"
MAX_LAG_DEPTH = 12


@dataclass
class Contribution:
    kpi: str
    period: str
    driver: str  # primitive name, or "baseline"
    signal: str | None  # series, "shock:<label>", or None
    value: float
    source_refs: list[str] = field(default_factory=list)


def _state_terms(rspec: ResolvedSpec, history: StateHistory, prim: str, period: str) -> list[tuple[str, float, list[str]]]:
    rho = {p.name: p.persistence for p in rspec.primitives}[prim]
    k = diff(period, history.latest_period)
    src = period if k <= 0 else history.latest_period
    decay = 1.0 if k <= 0 else rho**k
    est = history.get(prim, src)
    return [(s, decay * v, history.refs_for(s, src)) for s, v in est.contributions.items()]


def driver_waterfall(
    rspec: ResolvedSpec,
    history: StateHistory,
    models: dict[str, KPIModel],
    period: str,
    shocks: list[Shock] | tuple = (),
    reported: dict[str, dict[str, GroundTruth]] | None = None,
    _depth: int = 0,
) -> dict[str, list[Contribution]]:
    """reported: kpi -> period -> GroundTruth known at as_of (feeds lag terms)."""
    reported = reported or {}
    previous: dict[str, list[Contribution]] | None = None
    mean_b = {(e.source, e.target): e.prior_mean for e in rspec.primitive_edges}
    deltas = shock_deltas(rspec, list(shocks), period, mean_b) if shocks else {}
    shock_name = "shock:" + "+".join(s.label or s.primitive for s in shocks) if shocks else ""

    out: dict[str, list[Contribution]] = {}
    totals: dict[str, float] = {}
    formulas = rspec.formulas
    for kpi in rspec.kpi_order():
        rows: list[Contribution] = []
        if kpi in formulas:
            f = formulas[kpi]
            grad = f.gradient({n: totals[n] for n in f.names})
            for n in f.names:
                for c in out[n]:
                    if c.driver != BASELINE:
                        rows.append(Contribution(kpi, period, c.driver, c.signal, grad[n] * c.value, c.source_refs))
            level = float(f.evaluate({n: totals[n] for n in f.names}))
            rows.insert(0, Contribution(kpi, period, BASELINE, None, level - sum(r.value for r in rows)))
        else:
            m = models[kpi]
            rows.append(Contribution(kpi, period, BASELINE, None, float(m.coef_mean[0])))
            for j, prim in enumerate(m.parents):
                b = float(m.coef_mean[1 + j])
                for series, v, refs in _state_terms(rspec, history, prim, period):
                    rows.append(Contribution(kpi, period, prim, series, b * v, refs))
                if deltas and deltas.get(prim):
                    rows.append(Contribution(kpi, period, prim, shock_name, b * float(deltas[prim])))
            if m.has_lag:
                phi, prev = m.lag_coef, shift(period, -1)
                known = reported.get(kpi, {}).get(prev)
                if known is not None:
                    rows.append(Contribution(kpi, period, f"{kpi}[t-1]", None, phi * known.value, [known.source_ref]))
                elif lag_is_gap(reported, kpi, prev):
                    rows.append(Contribution(kpi, period, f"{kpi}[t-1]", "imputed:historical_mean", phi * m.y_mean))
                else:
                    if _depth >= MAX_LAG_DEPTH:
                        raise ValueError(f"{kpi}: no reported value within {MAX_LAG_DEPTH} periods before {period}")
                    if previous is None:
                        previous = driver_waterfall(rspec, history, models, prev, shocks, reported, _depth + 1)
                    rows += [Contribution(kpi, period, c.driver, c.signal, phi * c.value, c.source_refs)
                             for c in previous[kpi]]
        out[kpi] = rows
        totals[kpi] = sum(r.value for r in rows)
    return out
