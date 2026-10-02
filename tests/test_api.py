"""API smoke test against the local database. Skipped when no data has been ingested."""

import pytest

from adapters.http import data_root

pytestmark = pytest.mark.skipif(not (data_root() / "chui.sqlite").exists(), reason="no local database")


def test_api_twins_forecast_and_scenario():
    from fastapi.testclient import TestClient

    from api.serve import app

    c = TestClient(app)
    twins = c.get("/api/twins").json()
    assert any(t["ticker"] == "CMG" for t in twins)
    r = c.get("/api/twins/CMG/forecast", params={"paths": 1000, "shock": ["sentiment:2026Q4:-2:2"]})
    assert r.status_code == 200
    body = r.json()
    assert body["forecast"] and body["waterfall"]
    assert body["scenario"]["delta_mean"]["comps"]["2026Q4"] < 0  # bad news lowers comps
    assert c.get("/api/twins/NOPE").status_code == 404
