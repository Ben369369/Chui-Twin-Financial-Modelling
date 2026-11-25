"""Auto-sealing: expected release from the company's own history, the seal window, one seal per period."""

import importlib.util
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from engine.observation import GroundTruth
from engine.sealing import seal

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


auto = _load("auto_seal")
resolver = _load("resolve_sealed")
SPEC = SimpleNamespace(ticker="ZZZ", period="quarter", kpis={"growth": None})


def _gt(period, d):
    return GroundTruth("ZZZ", period, "growth", 1.0, datetime(d.year, d.month, d.day, 21, tzinfo=timezone.utc),
                       "test:ref", 1.0, True)


HISTORY = [_gt("2024Q4", date(2025, 2, 4)), _gt("2025Q4", date(2026, 2, 3)), _gt("2026Q3", date(2026, 10, 28))]


def test_expected_release_is_earliest_of_last_two_years_same_weekday():
    released = auto.release_dates(HISTORY)
    due = auto.expected_release(released, "2026Q4", "quarter")
    assert due == date(2027, 2, 2) and due.weekday() == date(2026, 2, 3).weekday()


def test_plan_waits_seals_then_skips(tmp_path):
    p = lambda today: auto.plan(SPEC, HISTORY, today, 10, tmp_path)  # noqa: E731
    assert p(date(2027, 1, 1))["action"] == "wait"
    assert p(date(2027, 1, 25))["action"] == "seal"
    assert p(date(2027, 2, 2))["action"] == "skip"


def test_seal_inside_window_counts_once(tmp_path):
    record = {"ticker": "ZZZ", "forecast": {"growth": {"2026Q4": {"p50": 1.0}}}}
    seal(record, tmp_path)  # sealed today, before the window: does not count for a later window
    assert auto.already_sealed("ZZZ", "2026Q4", date.today(), tmp_path) is not None
    assert auto.already_sealed("ZZZ", "2026Q4", date(2099, 1, 1), tmp_path) is None
    assert auto.already_sealed("ZZZ", "2027Q1", date.today(), tmp_path) is None


def test_headline_is_latest_valid_seal():
    rows = [{"ticker": "ZZZ", "kpi": "growth", "period": "2026Q4", "sealed_at": s, "status": st}
            for s, st in [("2026-10-18T19:00:51+00:00", "resolved"), ("2027-01-25T12:00:00+00:00", "resolved"),
                          ("2027-02-03T12:00:00+00:00", "invalid: outcome was public before the seal")]]
    assert [r["final"] for r in resolver.mark_final(rows)] == [False, True, False]
