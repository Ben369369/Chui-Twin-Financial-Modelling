"""Rule 3: nothing available after as_of may influence a fit."""

import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine.observation import GroundTruth, Observation, available_as_of
from engine.spec import load_spec
from engine.twin import Twin
from tests.synthetic import generate

ROOT = Path(__file__).resolve().parents[1]
AS_OF = datetime(2023, 11, 1, tzinfo=timezone.utc)


def _setup():
    rspec = load_spec(ROOT / "tests/fixtures/specs/dummy.yaml", ROOT / "templates")
    obs, gt, _, _ = generate(rspec, "2015Q1", "2024Q4")
    return rspec, obs, gt


def test_filter_handles_naive_and_aware():
    rows = [
        GroundTruth("X", "2020Q1", "k", 1.0, datetime(2020, 5, 1), "r"),
        GroundTruth("X", "2020Q2", "k", 1.0, datetime(2020, 8, 1, tzinfo=timezone.utc), "r"),
    ]
    assert len(available_as_of(rows, datetime(2020, 6, 1, tzinfo=timezone.utc))) == 1


def test_future_rows_do_not_change_the_fit():
    rspec, obs, gt = _setup()
    clean = Twin(rspec, obs, gt).fit(AS_OF)

    later = AS_OF + timedelta(seconds=1)
    # Poison: revised past observations and restated ground truth, both published after as_of.
    poisoned_obs = obs + [dataclasses.replace(o, value=1e6, available_at=later) for o in obs[::5]]
    poisoned_gt = gt + [dataclasses.replace(g, value=-1e6, available_at=later) for g in gt]
    dirty = Twin(rspec, poisoned_obs, poisoned_gt).fit(AS_OF)

    for key, est in clean.history.states.items():
        assert dirty.history.states[key].mean == est.mean
    for k, m in clean.models.items():
        assert (dirty.models[k].coef_mean == m.coef_mean).all()
    a = clean.forecast(n_paths=2000, seed=3).summary
    b = dirty.forecast(n_paths=2000, seed=3).summary
    assert a == b


def test_current_period_is_anchored_at_as_of():
    rspec, obs, gt = _setup()
    fitted = Twin(rspec, obs, gt).fit(AS_OF)
    assert fitted.history.latest_period == "2023Q4"
    reading = next(r for (s, p), r in fitted.history.readings.items() if p == "2023Q4")
    assert reading.anchor == AS_OF.date()
    # Ground truth for 2023Q3 is released 2023-10-30, so it is visible; 2023Q4 is not.
    assert fitted.next_unreported_period() == "2023Q4"


def test_lag_shifts_effective_date():
    from engine.estimation.weighted import _feature, _Series

    rspec, obs, _ = _setup()
    sig = next(s for s in rspec.signals if s.series == "syn:c")
    rows = [o for o in obs if o.series == "syn:c"]
    lag = 400
    anchor = AS_OF.date()
    with_lag = _feature(_Series(rows, lag), sig.model_copy(update={"lag_days": lag}), anchor)
    without = _feature(_Series(rows, 0), sig, anchor - timedelta(days=lag))
    assert with_lag[0] == without[0] and with_lag[1] == without[1]
