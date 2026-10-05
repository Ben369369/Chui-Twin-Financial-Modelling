"""The sealed-forecast resolver: hash check, outcome-after-seal rule, scoring against baselines."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine.observation import GroundTruth
from engine.sealing import seal
from storage import db

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("resolve_sealed", ROOT / "scripts" / "resolve_sealed.py")
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)

RECORD = {
    "ticker": "ZZZ",
    "forecast": {"growth": {"2026Q3": {"mean": 10.0, "sd": 2.0, "p10": 7.4, "p50": 10.0, "p90": 12.6}}},
    "expectation_gaps": [{"kpi": "growth", "period": "2026Q3", "source": "guidance", "expectation": 8.0}],
}


def _truth(conn, period, value, when):
    db.save_ground_truth(conn, [GroundTruth("ZZZ", period, "growth", value, when, "test:ref", 1.0, True)])


def test_resolves_after_report_and_scores_baselines(tmp_path):
    path, _ = seal(RECORD, tmp_path)
    conn = db.connect(tmp_path / "t.sqlite")
    now = datetime.now(timezone.utc)
    _truth(conn, "2026Q2", 6.0, now - timedelta(days=60))
    _truth(conn, "2025Q3", 12.0, now - timedelta(days=300))
    _truth(conn, "2026Q3", 11.0, now + timedelta(days=5))
    [row] = resolver.resolve(path, conn)
    assert row["hash_ok"] and row["status"] == "resolved" and row["inside_80"]
    assert row["baselines"] == {"guidance": 3.0, "last quarter": 5.0, "last year": 1.0}
    assert row["crps"] < 1.0
    assert "| ZZZ | growth | 2026Q3 |" in resolver.to_markdown([row])


def test_outcome_known_before_seal_is_invalid(tmp_path):
    conn = db.connect(tmp_path / "t.sqlite")
    _truth(conn, "2026Q3", 11.0, datetime.now(timezone.utc) - timedelta(days=1))
    path, _ = seal(RECORD, tmp_path)
    [row] = resolver.resolve(path, conn)
    assert row["status"].startswith("invalid")


def test_tampered_file_fails_hash(tmp_path):
    path, _ = seal(RECORD, tmp_path)
    path.write_text(path.read_text(encoding="utf-8").replace("10.0", "11.0", 1), encoding="utf-8")
    [row] = resolver.resolve(path, db.connect(tmp_path / "t.sqlite"))
    assert not row["hash_ok"]
