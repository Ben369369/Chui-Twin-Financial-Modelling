"""The engine must run end to end on a template whose names it has never seen."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from engine.attribution.counterfactual import leave_one_signal_out
from engine.evaluation.backtest import TWIN, walk_forward
from engine.observation import ExternalForecast
from engine.simulation.montecarlo import Shock
from engine.spec import load_spec
from engine.twin import Twin
from tests.synthetic import generate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def dummy():
    rspec = load_spec(ROOT / "tests/fixtures/specs/dummy.yaml", ROOT / "templates")
    obs, gt, truth, periods = generate(rspec, "2015Q1", "2024Q4")
    return rspec, obs, gt, truth, periods


def test_resolves_with_made_up_names(dummy):
    rspec = dummy[0]
    assert rspec.primitive_names == ["flux_q", "warp_z", "glim_7"]
    assert [(e.source, e.target) for e in rspec.primitive_edges] == [("warp_z", "flux_q")]
    assert rspec.kpi_order()[-1] == "zblx"


def test_states_track_the_truth(dummy):
    rspec, obs, gt, truth, periods = dummy
    fitted = Twin(rspec, obs, gt).fit(datetime(2025, 1, 15, tzinfo=timezone.utc))
    for prim in ("flux_q", "glim_7"):
        est = np.array([fitted.history.mean(prim, p) for p in periods])
        assert np.corrcoef(est, truth[prim])[0, 1] > 0.8


def test_forecast_waterfall_and_gap(dummy):
    rspec, obs, gt, _, _ = dummy
    ext = [ExternalForecast("ZZZ", "2025Q1", "zorp", "guess", 0.0,
                            datetime(2025, 1, 2, tzinfo=timezone.utc), "test")]
    fitted = Twin(rspec, obs, gt, ext).fit(datetime(2025, 1, 15, tzinfo=timezone.utc))
    fc = fitted.forecast(n_paths=20_000)
    # 2024Q4 is released 30 days after quarter end, so on Jan 15 it is still unreported.
    assert list(fc.summary["zorp"]) == ["2024Q4", "2025Q1"]
    for p in ("2024Q4", "2025Q1"):
        for k in ("zorp", "blix", "zblx"):
            total = sum(c.value for c in fc.waterfall[p][k])
            assert abs(total - fc.summary[k][p]["mean"]) < 0.1, (k, p)
    assert len(fc.gaps) == 1 and 0.0 <= fc.gaps[0].prob_above <= 1.0
    # Every non-baseline term carries sources.
    assert all(c.source_refs for c in fc.waterfall["2025Q1"]["zorp"] if c.driver == "flux_q")


def test_shock_propagates_through_edges(dummy):
    rspec, obs, gt, _, _ = dummy
    fitted = Twin(rspec, obs, gt).fit(datetime(2025, 1, 15, tzinfo=timezone.utc))
    base = fitted.forecast(["2025Q1"], n_paths=20_000, seed=1).summary["zorp"]["2025Q1"]["mean"]
    shocked = fitted.forecast(["2025Q1"], n_paths=20_000, seed=1,
                              shocks=[Shock("warp_z", "2025Q1", 2.0)]).summary["zorp"]["2025Q1"]["mean"]
    # warp_z -> flux_q (+0.5) -> zorp (+): a positive shock to warp_z raises zorp.
    assert shocked > base + 0.5


def test_backtest_beats_seasonal_naive(dummy):
    rspec, obs, gt, _, _ = dummy
    card = walk_forward(rspec, obs, gt, test_periods=[f"{y}Q{q}" for y in (2021, 2022, 2023) for q in (1, 2, 3, 4)],
                        n_paths=2000)
    table = {(r["kpi"], r["model"]): r for r in card.table()}
    assert table[("zorp", TWIN)]["crps"] < table[("zorp", "seasonal_naive")]["crps"]
    assert card.skill("naive_last")["zorp"] > 0


def test_leave_one_signal_out(dummy):
    rspec, obs, gt, _, _ = dummy
    impacts = leave_one_signal_out(rspec, obs, gt, datetime(2025, 1, 15, tzinfo=timezone.utc), "2025Q1", n_paths=2000)
    assert {i.series for i in impacts} == {s.series for s in rspec.signals}
    # syn:c is the only sensor of glim_7, which drives blix: removing it must matter.
    blix_c = next(i for i in impacts if i.series == "syn:c" and i.kpi == "blix")
    blix_d = next(i for i in impacts if i.series == "syn:d" and i.kpi == "blix")
    assert abs(blix_c.delta_mean) > abs(blix_d.delta_mean)
