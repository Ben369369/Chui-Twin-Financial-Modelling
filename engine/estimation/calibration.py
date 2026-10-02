"""Calibrate primitive -> KPI edges on reported history.

Each modeled KPI is a Bayesian linear regression on the states of its parent
primitives, plus optionally its own previous reported value:

    y_t = a + sum_j b_j * x_{j,t} [+ phi_1 * y_{t-1}] [+ phi_s * y_{t-s}] + e_t,   e_t ~ N(0, sigma^2)

where s is one year of periods (seasonal lag).

Edge priors are in standardized units, so b_j ~ N(prior_mean * sd_y, (prior_sd * sd_y)^2).
phi is unitless and takes its prior directly. With no history the model is the prior.
See docs/model.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from engine.estimation.weighted import StateHistory
from engine.observation import ExternalForecast, GroundTruth, as_utc
from engine.periods import periods_per_year, shift
from engine.primitives import LagPrior
from engine.spec import ResolvedSpec

INTERCEPT_PRIOR_SDS = 2.0
NOISE_PRIOR_DOF = 2.0
CHANGE_DRIFT_PRIOR_SDS = 0.1
MIN_ANCHORED_PERIODS = 3
ANCHOR_BIAS_PRIOR_SDS = 1.0


@dataclass
class KPIModel:
    kpi: str
    parents: list[str]
    lags: list[int]  # e.g. [1] for y[t-1], [1, 4] adds the same quarter last year
    target: str  # "level", or "change": coefficients apply to y[t]-anchor[t] and state changes
    coef_mean: np.ndarray  # [intercept, b_1, ..., b_m, phi_lag1, ...]
    coef_cov: np.ndarray
    sigma: float
    n_obs: int
    y_mean: float
    y_sd: float
    periods_used: list[str]
    anchor: str = "last_reported"
    n_anchored: int = 0  # training periods anchored on the external source

    @property
    def has_lag(self) -> bool:
        return bool(self.lags)

    @property
    def needs_previous(self) -> bool:
        return self.has_lag or self.target == "change"

    def lag_coef(self, k: int) -> float:
        return float(self.coef_mean[1 + len(self.parents) + self.lags.index(k)])


def latest_by_period(rows: list[GroundTruth], entity_id: str, kpi: str) -> dict[str, GroundTruth]:
    """One value per period; a later restatement replaces an earlier report."""
    out: dict[str, GroundTruth] = {}
    for r in sorted(rows, key=lambda r: r.available_at):
        if r.entity_id == entity_id and r.kpi == kpi:
            out[r.period] = r
    return out


def _posterior(X: np.ndarray, y: np.ndarray, m0: np.ndarray, prior_var: np.ndarray, s0: float):
    n = len(y)
    L0 = np.diag(1.0 / prior_var)
    sigma2 = s0**2
    for _ in range(50):
        cov = np.linalg.inv(X.T @ X / sigma2 + L0)
        mean = cov @ (X.T @ y / sigma2 + L0 @ m0)
        ssr = float(np.sum((y - X @ mean) ** 2)) if n else 0.0
        new = (ssr + NOISE_PRIOR_DOF * s0**2) / (n + NOISE_PRIOR_DOF)
        done = abs(new - sigma2) < 1e-10 * max(sigma2, 1e-12)
        sigma2 = new
        if done:
            break
    cov = np.linalg.inv(X.T @ X / sigma2 + L0)
    mean = cov @ (X.T @ y / sigma2 + L0 @ m0)
    return mean, (cov + cov.T) / 2, float(np.sqrt(sigma2))


def lag_priors(rspec: ResolvedSpec, kpi: str) -> list[tuple[int, LagPrior]]:
    d = rspec.kpis[kpi]
    out = []
    if d.lag is not None:
        out.append((1, d.lag))
    if d.seasonal_lag is not None:
        out.append((periods_per_year(rspec.period), d.seasonal_lag))
    return out


def anchor_forecast(external: list[ExternalForecast], entity_id: str, source: str, kpi: str, period: str,
                    before: datetime | None = None) -> ExternalForecast | None:
    """Latest external forecast for (source, kpi, period), optionally published before a time."""
    cands = [e for e in external if e.source == source and e.kpi == kpi and e.period == period
             and e.entity_id == entity_id and (before is None or as_utc(e.available_at) < as_utc(before))]
    return max(cands, key=lambda e: e.available_at) if cands else None


def fit_kpi_models(
    rspec: ResolvedSpec,
    history: StateHistory,
    ground_truth: list[GroundTruth],
    external: list[ExternalForecast] | tuple = (),
) -> dict[str, KPIModel]:
    models: dict[str, KPIModel] = {}
    for kpi in rspec.modeled_kpis:
        if rspec.kpis[kpi].target == "change":
            models[kpi] = _fit_change(rspec, kpi, history, ground_truth, list(external))
            continue
        lags = lag_priors(rspec, kpi)
        edges = [e for e in rspec.kpi_edges if e.target == kpi]
        parents = [e.source for e in edges]
        rows = latest_by_period(ground_truth, rspec.ticker, kpi)

        def usable(p: str) -> bool:
            needed = [p] + [shift(p, -k) for k, _ in lags]
            if any(q in rspec.excluded_periods for q in needed):
                return False
            if p not in history.periods or not all(history.get(pr, p) for pr in parents):
                return False
            return all(shift(p, -k) in rows for k, _ in lags)

        periods = [p for p in sorted(rows) if usable(p)]
        y = np.array([rows[p].value for p in periods], dtype=float)
        X = np.ones((len(periods), 1 + len(parents) + len(lags)))
        for j, pr in enumerate(parents):
            X[:, 1 + j] = [history.mean(pr, p) for p in periods]
        for i, (k, _) in enumerate(lags):
            X[:, 1 + len(parents) + i] = [rows[shift(p, -k)].value for p in periods]

        n = len(y)
        y_mean = float(y.mean()) if n else 0.0
        y_sd = max(float(y.std(ddof=1)) if n >= 3 else 1.0, 1e-6)

        a0 = y_mean * (1.0 - sum(lp.prior_mean for _, lp in lags))
        m0 = [a0] + [e.prior_mean * y_sd for e in edges] + [lp.prior_mean for _, lp in lags]
        pv = ([(INTERCEPT_PRIOR_SDS * y_sd) ** 2] + [(e.prior_sd * y_sd) ** 2 for e in edges]
              + [lp.prior_sd**2 for _, lp in lags])
        mean, cov, sigma = _posterior(X, y, np.array(m0), np.array(pv), y_sd)

        models[kpi] = KPIModel(
            kpi=kpi,
            parents=parents,
            lags=[k for k, _ in lags],
            target="level",
            coef_mean=mean,
            coef_cov=cov,
            sigma=sigma,
            n_obs=n,
            y_mean=y_mean,
            y_sd=y_sd,
            periods_used=periods,
        )
    return models


def _fit_change(rspec: ResolvedSpec, kpi: str, history: StateHistory, ground_truth: list[GroundTruth],
                external: list[ExternalForecast]) -> KPIModel:
    """y_t - anchor_t = a + sum_j b_j * dx_{j,t} + e, where anchor_t is y_{t-1} or, with an external
    anchor, the latest forecast from that source published before y_t was reported.
    Priors on b scale with sd of the target; a is centered at 0."""
    edges = [e for e in rspec.kpi_edges if e.target == kpi]
    parents = [e.source for e in edges]
    rows = latest_by_period(ground_truth, rspec.ticker, kpi)
    source = rspec.kpis[kpi].anchor

    def usable(p: str) -> bool:
        q = shift(p, -1)
        if p in rspec.excluded_periods or q in rspec.excluded_periods or q not in rows:
            return False
        return all(history.get(pr, p) and history.get(pr, q) for pr in parents)

    def anchor(p: str) -> float | None:
        if source == "last_reported":
            return None
        f = anchor_forecast(external, rspec.ticker, source, kpi, p, before=rows[p].available_at)
        return f.value if f else None

    periods = [p for p in sorted(rows) if usable(p)]
    anchored = [p for p in periods if anchor(p) is not None]
    # With enough anchored history, fit the surprise model on anchored periods only:
    # surprises versus guidance and changes versus last quarter have different spreads.
    if len(anchored) >= MIN_ANCHORED_PERIODS:
        periods = anchored
    base = {p: (a if (a := anchor(p)) is not None else rows[shift(p, -1)].value) for p in periods}
    dy = np.array([rows[p].value - base[p] for p in periods], dtype=float)
    X = np.ones((len(periods), 1 + len(parents)))
    for j, pr in enumerate(parents):
        X[:, 1 + j] = [history.mean(pr, p) - history.mean(pr, shift(p, -1)) for p in periods]
    n = len(dy)
    levels = [r.value for r in rows.values()]
    sd = max(float(dy.std(ddof=1)) if n >= 3 else 1.0, 1e-6)
    m0 = np.array([0.0] + [e.prior_mean * sd for e in edges])
    # Versus last quarter, a rate cannot drift forever: keep the intercept near 0. Versus an
    # external forecast, a systematic gap is real (companies tend to beat their own guidance),
    # so the intercept is free to learn it.
    drift_sds = CHANGE_DRIFT_PRIOR_SDS if source == "last_reported" else ANCHOR_BIAS_PRIOR_SDS
    pv = np.array([(drift_sds * sd) ** 2] + [(e.prior_sd * sd) ** 2 for e in edges])
    mean, cov, sigma = _posterior(X, dy, m0, pv, sd)
    return KPIModel(kpi=kpi, parents=parents, lags=[], target="change", coef_mean=mean, coef_cov=cov,
                    sigma=sigma, n_obs=n, y_mean=float(np.mean(levels)) if levels else 0.0, y_sd=sd,
                    periods_used=periods, anchor=source, n_anchored=len([p for p in periods if p in anchored]))
