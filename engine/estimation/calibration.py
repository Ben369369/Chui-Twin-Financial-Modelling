"""Calibrate primitive -> KPI edges on reported history.

Each modeled KPI is a Bayesian linear regression on the states of its parent
primitives, plus optionally its own previous reported value:

    y_t = a + sum_j b_j * x_{j,t} [+ phi * y_{t-1}] + e_t,   e_t ~ N(0, sigma^2)

Edge priors are in standardized units, so b_j ~ N(prior_mean * sd_y, (prior_sd * sd_y)^2).
phi is unitless and takes its prior directly. With no history the model is the prior.
See docs/model.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.estimation.weighted import StateHistory
from engine.observation import GroundTruth
from engine.periods import shift
from engine.spec import ResolvedSpec

INTERCEPT_PRIOR_SDS = 2.0
NOISE_PRIOR_DOF = 2.0


@dataclass
class KPIModel:
    kpi: str
    parents: list[str]
    has_lag: bool
    coef_mean: np.ndarray  # [intercept, b_1, ..., b_m, (phi)]
    coef_cov: np.ndarray
    sigma: float
    n_obs: int
    y_mean: float
    y_sd: float
    periods_used: list[str]

    @property
    def lag_coef(self) -> float:
        return float(self.coef_mean[-1]) if self.has_lag else 0.0


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


def fit_kpi_models(
    rspec: ResolvedSpec,
    history: StateHistory,
    ground_truth: list[GroundTruth],
) -> dict[str, KPIModel]:
    models: dict[str, KPIModel] = {}
    for kpi in rspec.modeled_kpis:
        lag = rspec.kpis[kpi].lag
        edges = [e for e in rspec.kpi_edges if e.target == kpi]
        parents = [e.source for e in edges]
        rows = latest_by_period(ground_truth, rspec.ticker, kpi)

        def usable(p: str) -> bool:
            if p in rspec.excluded_periods or (lag is not None and shift(p, -1) in rspec.excluded_periods):
                return False
            if p not in history.periods or not all(history.get(pr, p) for pr in parents):
                return False
            return lag is None or shift(p, -1) in rows

        periods = [p for p in sorted(rows) if usable(p)]
        y = np.array([rows[p].value for p in periods], dtype=float)
        X = np.ones((len(periods), 1 + len(parents) + (lag is not None)))
        for j, pr in enumerate(parents):
            X[:, 1 + j] = [history.mean(pr, p) for p in periods]
        if lag is not None:
            X[:, -1] = [rows[shift(p, -1)].value for p in periods]

        n = len(y)
        y_mean = float(y.mean()) if n else 0.0
        y_sd = max(float(y.std(ddof=1)) if n >= 3 else 1.0, 1e-6)

        a0 = y_mean * (1.0 - lag.prior_mean) if lag is not None else y_mean
        m0 = [a0] + [e.prior_mean * y_sd for e in edges]
        pv = [(INTERCEPT_PRIOR_SDS * y_sd) ** 2] + [(e.prior_sd * y_sd) ** 2 for e in edges]
        if lag is not None:
            m0.append(lag.prior_mean)
            pv.append(lag.prior_sd**2)
        mean, cov, sigma = _posterior(X, y, np.array(m0), np.array(pv), y_sd)

        models[kpi] = KPIModel(
            kpi=kpi,
            parents=parents,
            has_lag=lag is not None,
            coef_mean=mean,
            coef_cov=cov,
            sigma=sigma,
            n_obs=n,
            y_mean=y_mean,
            y_sd=y_sd,
            periods_used=periods,
        )
    return models
