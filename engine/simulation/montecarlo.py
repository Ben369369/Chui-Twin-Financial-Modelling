"""Vectorized Monte Carlo over primitive states and KPIs.

Per path:
  - start states ~ N(estimated mean, estimated variance)
  - each step: x <- rho * x + innovation, where a primitive's innovation is its
    own N(0, 1 - rho^2) draw plus b_e times each parent's innovation
    (b_e sampled once per path from the edge prior)
  - scenario shocks add a decaying delta to a primitive, propagated to
    children through the same sampled edge coefficients
  - modeled KPIs = sampled regression coefficients . [1, parent states, (y[t-k] per lag)] + noise,
    where y[t-k] is the reported value if known at as_of, else the path's own simulated value
  - formula KPIs evaluated element-wise on the sampled components
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from engine.estimation.calibration import KPIModel
from engine.estimation.weighted import StateHistory
from engine.periods import diff, shift, span
from engine.spec import ResolvedSpec


@dataclass(frozen=True)
class Shock:
    primitive: str
    period: str
    size: float  # in standardized (sd) units of the primitive
    half_life_periods: float = 1.0
    label: str = ""


@dataclass
class SimulationResult:
    periods: list[str]
    kpis: dict[str, np.ndarray]  # kpi -> (n_paths, n_periods)
    states: dict[str, np.ndarray]  # primitive -> (n_paths, n_periods)
    n_paths: int
    seed: int
    shocks: list[Shock] = field(default_factory=list)
    clipped: dict[str, dict[str, float]] = field(default_factory=dict)  # kpi -> period -> share of paths

    def quantiles(self, kpi: str, period: str, qs=(0.1, 0.5, 0.9)) -> list[float]:
        col = self.kpis[kpi][:, self.periods.index(period)]
        return [float(v) for v in np.quantile(col, qs)]

    def summary(self) -> dict[str, dict[str, dict[str, float]]]:
        out: dict[str, dict[str, dict[str, float]]] = {}
        for k, arr in self.kpis.items():
            out[k] = {}
            for i, p in enumerate(self.periods):
                p10, p50, p90 = np.quantile(arr[:, i], (0.1, 0.5, 0.9))
                out[k][p] = {
                    "p10": float(p10),
                    "p50": float(p50),
                    "p90": float(p90),
                    "mean": float(arr[:, i].mean()),
                    "sd": float(arr[:, i].std()),
                }
                share = self.clipped.get(k, {}).get(p, 0.0)
                if share > 0:
                    out[k][p]["clipped_share"] = share
        return out


def _mvn(rng: np.random.Generator, mean: np.ndarray, cov: np.ndarray, n: int) -> np.ndarray:
    jitter = 1e-12 * max(float(np.trace(cov)), 1e-12)
    L = np.linalg.cholesky(cov + jitter * np.eye(len(mean)))
    return mean + rng.standard_normal((n, len(mean))) @ L.T


def lag_is_gap(reported: dict[str, dict], kpi: str, prev: str) -> bool:
    """True when y[t-1] is missing although period prev has already been reported
    (the company released results but did not disclose this KPI), or the KPI was
    never reported. Such gaps are imputed with the KPI's historical mean."""
    if not reported.get(kpi):
        return True
    released = [p for by_p in reported.values() for p in by_p]
    latest = max(released, key=lambda p: diff(p, prev))
    # Anything at or before the latest released period is in the past: missing means undisclosed.
    return diff(prev, latest) <= 0


def shock_deltas(
    rspec: ResolvedSpec,
    shocks: list[Shock],
    period: str,
    edge_coefs: dict[tuple[str, str], np.ndarray | float],
) -> dict[str, np.ndarray | float]:
    """Deterministic shock deltas at one period, propagated along primitive edges."""
    delta: dict[str, np.ndarray | float] = {p: 0.0 for p in rspec.primitive_names}
    for s in shocks:
        if s.primitive not in delta:
            raise ValueError(f"shock on unknown primitive {s.primitive!r}")
        k = diff(period, s.period)
        if k >= 0:
            delta[s.primitive] = delta[s.primitive] + s.size * 0.5 ** (k / s.half_life_periods)
    for child in rspec.primitive_order():
        for e in rspec.primitive_edges:
            if e.target == child:
                delta[child] = delta[child] + edge_coefs[(e.source, e.target)] * delta[e.source]
    return delta


def simulate(
    rspec: ResolvedSpec,
    history: StateHistory,
    models: dict[str, KPIModel],
    periods: list[str],
    n_paths: int = 10_000,
    seed: int = 0,
    shocks: list[Shock] | tuple = (),
    reported: dict[str, dict[str, float]] | None = None,
    anchors: dict[str, dict[str, float]] | None = None,
) -> SimulationResult:
    """reported: kpi -> period -> value known at as_of; feeds lag terms.
    anchors: kpi -> period -> external forecast value known at as_of, for anchored change KPIs."""
    rng = np.random.default_rng(seed)
    shocks = list(shocks)
    prims = rspec.primitive_names
    order = rspec.primitive_order()
    rho = {p.name: p.persistence for p in rspec.primitives}
    origin = history.latest_period

    edge_b = {
        (e.source, e.target): rng.normal(e.prior_mean, e.prior_sd, n_paths) for e in rspec.primitive_edges
    }
    parents = {c: [e for e in rspec.primitive_edges if e.target == c] for c in prims}

    def draw(period: str) -> dict[str, np.ndarray]:
        out = {}
        for p in prims:
            est = history.get(p, period)
            out[p] = rng.normal(est.mean, np.sqrt(est.variance), n_paths)
        return out

    # Walk forward from the origin once; record states for requested periods.
    targets = sorted(periods, key=lambda p: diff(p, origin))
    x = draw(origin)
    step = 0
    state_at: dict[str, dict[str, np.ndarray]] = {}
    for t in targets:
        k = diff(t, origin)
        if k <= 0:
            if history.get(prims[0], t) is None:
                raise ValueError(f"no state estimate for past period {t}")
            state_at[t] = x if k == 0 else draw(t)
            continue
        while step < k:
            innov: dict[str, np.ndarray] = {}
            for p in order:
                e = np.sqrt(1.0 - rho[p] ** 2) * rng.standard_normal(n_paths)
                for edge in parents[p]:
                    e = e + edge_b[(edge.source, edge.target)] * innov[edge.source]
                innov[p] = e
            x = {p: rho[p] * x[p] + innov[p] for p in prims}
            step += 1
        state_at[t] = x

    reported = reported or {}
    # Lag terms chain through unreported periods, so simulate every period from the
    # first unreported one up to the last requested; output only what was asked for.
    released = [p for by_p in reported.values() for p in by_p]
    if any(m.needs_previous for m in models.values()) and released:
        first_open = shift(max(released, key=lambda p: diff(p, origin)), 1)
        last = max(periods, key=lambda p: diff(p, origin))
        extra = [p for p in span(first_open, last) if p not in periods]
        if extra:
            full = simulate(rspec, history, models, list(periods) + extra, n_paths, seed, shocks, reported, anchors)
            keep = [full.periods.index(p) for p in periods]
            return SimulationResult(list(periods), {k: v[:, keep] for k, v in full.kpis.items()},
                                    {k: v[:, keep] for k, v in full.states.items()}, n_paths, seed, shocks,
                                    {k: {p: c for p, c in by.items() if p in periods} for k, by in full.clipped.items()})
    coefs = {k: _mvn(rng, m.coef_mean, m.coef_cov, n_paths) for k, m in models.items()}
    kpi_out = {k: np.empty((n_paths, len(periods))) for k in rspec.kpi_order()}
    state_out = {p: np.empty((n_paths, len(periods))) for p in prims}
    formulas = rspec.formulas
    simulated: dict[str, dict[str, np.ndarray]] = {}
    clipped: dict[str, dict[str, float]] = {}
    sim_states: dict[str, dict[str, np.ndarray]] = {}

    def change_input(prim: str, t: str, x_t: np.ndarray, d_t) -> np.ndarray | float:
        """State change since t-1 for change-target KPIs. Where both periods are estimated,
        use estimated means (as calibration does) so state noise is not double counted."""
        prev = shift(t, -1)
        est_t, est_p = history.get(prim, t), history.get(prim, prev)
        if est_t is not None and est_p is not None:
            d_p = shock_deltas(rspec, shocks, prev, edge_b)[prim] if shocks else 0.0
            return (est_t.mean + d_t) - (est_p.mean + d_p)
        if prev in sim_states:
            return x_t - sim_states[prev][prim]
        return x_t - (est_p.mean if est_p is not None else 0.0)

    def lagged(kpi: str, t: str, k: int) -> np.ndarray | float:
        prev = shift(t, -k)
        if prev in reported.get(kpi, {}):
            return reported[kpi][prev]
        if prev in simulated:
            return simulated[prev][kpi]
        if lag_is_gap(reported, kpi, prev):
            return models[kpi].y_mean
        raise ValueError(f"{kpi} needs a value for {prev}: not reported and not simulated in this run")

    for t in sorted(periods, key=lambda p: diff(p, origin)):  # chronological, so lags are ready
        i = periods.index(t)
        d = shock_deltas(rspec, shocks, t, edge_b) if shocks else {p: 0.0 for p in prims}
        xs = {p: state_at[t][p] + d[p] for p in prims}
        for p in prims:
            state_out[p][:, i] = xs[p]
        values: dict[str, np.ndarray] = {}
        for k in rspec.kpi_order():
            if k in formulas:
                values[k] = np.broadcast_to(formulas[k].evaluate(values), (n_paths,))
            else:
                m, c = models[k], coefs[k]
                y = c[:, 0].copy()
                for j, pr in enumerate(m.parents):
                    y += c[:, 1 + j] * (change_input(pr, t, xs[pr], d[pr]) if m.target == "change" else xs[pr])
                if m.target == "change":
                    anchored = (anchors or {}).get(k, {}).get(t)
                    y += anchored if anchored is not None else lagged(k, t, 1)
                for li, lag in enumerate(m.lags):
                    y += c[:, 1 + len(m.parents) + li] * lagged(k, t, lag)
                values[k] = y + m.sigma * rng.standard_normal(n_paths)
            bounds = rspec.kpis[k].bounds
            if bounds is not None:
                lo = -np.inf if bounds[0] is None else bounds[0]
                hi = np.inf if bounds[1] is None else bounds[1]
                v = np.asarray(values[k], dtype=float)
                share = float(np.mean((v < lo) | (v > hi)))
                if share > 0:
                    clipped.setdefault(k, {})[t] = share
                values[k] = np.clip(v, lo, hi)  # clip before storing so later lags see valid values
            kpi_out[k][:, i] = values[k]
        simulated[t] = values
        sim_states[t] = xs

    return SimulationResult(periods=list(periods), kpis=kpi_out, states=state_out, n_paths=n_paths, seed=seed, shocks=shocks,
                            clipped=clipped)
