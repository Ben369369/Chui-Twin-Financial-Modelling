"""Twin: the company-agnostic pipeline from observations to a forecast.

    Twin(spec, observations, ground_truth).fit(as_of).forecast(periods)

fit() applies the point-in-time cut, estimates states and calibrates KPI
edges. forecast() simulates, summarizes, attributes and compares against
any external forecasts (the expectation gap).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from engine.attribution.waterfall import Contribution, driver_waterfall
from engine.estimation.calibration import KPIModel, anchor_forecast, fit_kpi_models, latest_by_period
from engine.estimation.weighted import StateHistory, estimate_states
from engine.observation import ExternalForecast, GroundTruth, Observation, as_utc, available_as_of
from engine.periods import period_of, periods_per_year, shift
from engine.simulation.montecarlo import Shock, SimulationResult, simulate
from engine.spec import ResolvedSpec

DEFAULT_LOOKBACK_YEARS = 10


@dataclass
class ExpectationGap:
    kpi: str
    period: str
    source: str
    expectation: float
    gap_mean: float  # E[X_sim] - X_mkt
    prob_above: float  # P(X_sim > X_mkt)
    source_ref: str


@dataclass
class Forecast:
    fitted: "FittedTwin"
    sim: SimulationResult
    summary: dict[str, dict[str, dict[str, float]]]
    waterfall: dict[str, dict[str, list[Contribution]]]  # period -> kpi -> rows
    gaps: list[ExpectationGap] = field(default_factory=list)

    def to_record(self) -> dict:
        """JSON-safe record used for sealing and the API."""
        f = self.fitted
        return {
            "ticker": f.rspec.ticker,
            "spec_hash": f.rspec.spec_hash(),
            "as_of": f.as_of.isoformat(),
            "n_paths": self.sim.n_paths,
            "seed": self.sim.seed,
            "shocks": [s.__dict__ for s in self.sim.shocks],
            "forecast": self.summary,
            "states": {
                p: {prim: {"mean": f.history.get(prim, p).mean, "variance": f.history.get(prim, p).variance}
                    for prim in f.rspec.primitive_names}
                for p in f.history.periods[-4:]
            },
            "kpi_models": {
                k: {"parents": m.parents, "lags": m.lags, "coef_mean": m.coef_mean.tolist(), "sigma": m.sigma,
                    "n_obs": m.n_obs}
                for k, m in f.models.items()
            },
            "waterfall": {
                p: {k: [c.__dict__ for c in rows] for k, rows in by_kpi.items()}
                for p, by_kpi in self.waterfall.items()
            },
            "expectation_gaps": [g.__dict__ for g in self.gaps],
        }


@dataclass
class FittedTwin:
    rspec: ResolvedSpec
    as_of: datetime
    history: StateHistory
    models: dict[str, KPIModel]
    ground_truth: list[GroundTruth]
    external: list[ExternalForecast]

    def next_unreported_period(self) -> str:
        reported = [g.period for g in self.ground_truth if g.entity_id == self.rspec.ticker]
        if reported:
            return shift(max(reported), 1)
        return period_of(self.as_of.date(), self.rspec.period)

    def anchors(self, periods: list[str]) -> dict[str, dict[str, ExternalForecast]]:
        """External forecasts that anchored change KPIs start from, as known at as_of."""
        out: dict[str, dict[str, ExternalForecast]] = {}
        for k, d in self.rspec.kpis.items():
            if d.target != "change" or d.anchor == "last_reported":
                continue
            for p in periods:
                f = anchor_forecast(self.external, self.rspec.ticker, d.anchor, k, p)
                if f is not None:
                    out.setdefault(k, {})[p] = f
        return out

    def reported(self) -> dict[str, dict[str, GroundTruth]]:
        return {k: latest_by_period(self.ground_truth, self.rspec.ticker, k) for k in self.rspec.kpis}

    def forecast(
        self,
        periods: list[str] | None = None,
        n_paths: int = 10_000,
        seed: int = 0,
        shocks: list[Shock] | tuple = (),
    ) -> Forecast:
        if periods is None:
            first = self.next_unreported_period()
            periods = [first, shift(first, 1)]
        reported = self.reported()
        values = {k: {p: g.value for p, g in by_p.items()} for k, by_p in reported.items()}
        anchors = self.anchors(periods)
        sim = simulate(self.rspec, self.history, self.models, periods, n_paths=n_paths, seed=seed, shocks=shocks,
                       reported=values, anchors={k: {p: f.value for p, f in by.items()} for k, by in anchors.items()})
        waterfall = {p: driver_waterfall(self.rspec, self.history, self.models, p, shocks, reported, anchors)
                     for p in periods}
        gaps = []
        for ext in self._latest_external(periods):
            col = sim.kpis[ext.kpi][:, periods.index(ext.period)]
            gaps.append(
                ExpectationGap(
                    kpi=ext.kpi,
                    period=ext.period,
                    source=ext.source,
                    expectation=ext.value,
                    gap_mean=float(col.mean() - ext.value),
                    prob_above=float(np.mean(col > ext.value)),
                    source_ref=ext.source_ref,
                )
            )
        return Forecast(self, sim, sim.summary(), waterfall, gaps)

    def _latest_external(self, periods: list[str]) -> list[ExternalForecast]:
        latest: dict[tuple[str, str, str], ExternalForecast] = {}
        for e in sorted(self.external, key=lambda e: e.available_at):
            if e.entity_id == self.rspec.ticker and e.period in periods and e.kpi in self.rspec.kpis:
                latest[(e.source, e.kpi, e.period)] = e
        return list(latest.values())


class Twin:
    def __init__(
        self,
        rspec: ResolvedSpec,
        observations: list[Observation],
        ground_truth: list[GroundTruth],
        external: list[ExternalForecast] | tuple = (),
    ):
        self.rspec = rspec
        self.observations = observations
        self.ground_truth = ground_truth
        self.external = list(external)

    def fit(self, as_of: datetime, start_period: str | None = None, min_history: int = 6) -> FittedTwin:
        as_of = as_utc(as_of)
        gt = [g for g in available_as_of(self.ground_truth, as_of) if g.entity_id == self.rspec.ticker]
        start = start_period or self.rspec.history_start
        if start is None:
            start = shift(
                period_of(as_of.date(), self.rspec.period),
                -DEFAULT_LOOKBACK_YEARS * periods_per_year(self.rspec.period),
            )
        history = estimate_states(self.rspec, self.observations, as_of, start, min_history=min_history)
        external = available_as_of(self.external, as_of)
        models = fit_kpi_models(self.rspec, history, gt, external)
        return FittedTwin(
            rspec=self.rspec,
            as_of=as_of,
            history=history,
            models=models,
            ground_truth=gt,
            external=external,
        )
