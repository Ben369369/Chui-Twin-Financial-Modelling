import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from engine.evaluation.baselines import baseline_forecasts
from engine.evaluation.metrics import crps_gaussian, crps_samples
from engine.observation import GroundTruth
from engine.sealing import seal, verify
from engine.spec import load_spec
from engine.twin import Twin
from tests.synthetic import generate

ROOT = Path(__file__).resolve().parents[1]


def _fitted():
    rspec = load_spec(ROOT / "tests/fixtures/specs/dummy.yaml", ROOT / "templates")
    obs, gt, _, _ = generate(rspec, "2015Q1", "2024Q4")
    return Twin(rspec, obs, gt).fit(datetime(2025, 1, 15, tzinfo=timezone.utc))


def test_ten_thousand_paths_under_two_seconds():
    fitted = _fitted()
    fitted.forecast(n_paths=1000)  # warm up
    t0 = time.perf_counter()
    fc = fitted.forecast(["2025Q1", "2025Q2", "2025Q3", "2025Q4"], n_paths=10_000)
    assert time.perf_counter() - t0 < 2.0
    assert fc.sim.kpis["zorp"].shape == (10_000, 4)


def test_seed_reproducible_and_uncertainty_grows():
    fitted = _fitted()
    a = fitted.forecast(["2025Q1", "2025Q4"], n_paths=5000, seed=11).summary
    b = fitted.forecast(["2025Q1", "2025Q4"], n_paths=5000, seed=11).summary
    assert a == b
    assert a["zorp"]["2025Q4"]["sd"] > a["zorp"]["2025Q1"]["sd"]


def test_crps_samples_matches_gaussian():
    rng = np.random.default_rng(0)
    x = rng.normal(1.0, 2.0, 200_000)
    for y in (-3.0, 1.0, 4.0):
        assert abs(crps_samples(x, y) - crps_gaussian(1.0, 2.0, y)) < 0.01
    assert crps_samples(np.array([2.0, 2.0]), 5.0) == 3.0  # point mass = absolute error


def test_baselines():
    t = datetime(2020, 1, 1, tzinfo=timezone.utc)
    rows = [GroundTruth("X", f"{y}Q{q}", "k", float(y * 10 + q), t, f"r{y}{q}") for y in (2020, 2021) for q in (1, 2, 3, 4)]
    out = {b.name: b for b in baseline_forecasts(["naive_last", "seasonal_naive"], "quarter", "X", "k", "2022Q1", rows, [])}
    assert out["naive_last"].value == 20214 and out["seasonal_naive"].value == 20211
    assert out["seasonal_naive"].sd == 10.0  # every seasonal error is exactly 10


def test_seal_roundtrip(tmp_path):
    record = _fitted().forecast(n_paths=500).to_record()
    path, digest = seal(record, tmp_path)
    assert verify(path) == digest
