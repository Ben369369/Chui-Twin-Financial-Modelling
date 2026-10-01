"""SQLite store for development. Same schema as the Postgres deployment (migrations/)."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from adapters.http import data_root
from engine.observation import ExternalForecast, GroundTruth, Observation, RawSnapshot, as_utc

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(path) if path else data_root() / "chui.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)")
    done = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    for f in sorted(MIGRATIONS.glob("*.sql")):
        if f.name not in done:
            conn.executescript(f.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations VALUES (?)", (f.name,))
    conn.commit()
    return conn


def _ts(t: datetime) -> str:
    return as_utc(t).isoformat()


def save_snapshots(conn: sqlite3.Connection, snaps: list[RawSnapshot]) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO raw_snapshots VALUES (?,?,?,?,?,?,?)",
        [(s.sha256, s.source, _ts(s.fetched_at), s.path, s.sha256, s.url, json.dumps(s.params)) for s in snaps],
    )
    conn.commit()


def save_observations(conn: sqlite3.Connection, obs: list[Observation]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?,?,?,?)",
        [(o.entity_id, o.source, o.series, o.observed_at.isoformat(), _ts(o.available_at), o.value, o.unit, o.geo,
          o.source_ref) for o in obs],
    )
    conn.commit()


def load_observations(conn: sqlite3.Connection, series: list[str] | None = None) -> list[Observation]:
    q, args = "SELECT * FROM observations", []
    if series:
        q += f" WHERE series IN ({','.join('?' * len(series))})"
        args = list(series)
    return [
        Observation(e, s, se, date.fromisoformat(oa), datetime.fromisoformat(aa), v, u, g, r)
        for e, s, se, oa, aa, v, u, g, r in conn.execute(q, args)
    ]


def save_ground_truth(conn: sqlite3.Connection, rows: list[GroundTruth]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO ground_truth VALUES (?,?,?,?,?,?,?,?)",
        [(g.entity_id, g.period, g.kpi, g.value, _ts(g.available_at), g.source_ref, g.confidence, int(g.verified))
         for g in rows],
    )
    conn.commit()


def load_ground_truth(conn: sqlite3.Connection, entity_id: str) -> list[GroundTruth]:
    return [
        GroundTruth(e, p, k, v, datetime.fromisoformat(a), r, c, bool(ver))
        for e, p, k, v, a, r, c, ver in conn.execute("SELECT * FROM ground_truth WHERE entity_id = ?", (entity_id,))
    ]


def save_external(conn: sqlite3.Connection, rows: list[ExternalForecast]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO external_forecasts VALUES (?,?,?,?,?,?,?)",
        [(x.entity_id, x.period, x.kpi, x.source, x.value, _ts(x.available_at), x.source_ref) for x in rows],
    )
    conn.commit()


def load_external(conn: sqlite3.Connection, entity_id: str) -> list[ExternalForecast]:
    return [
        ExternalForecast(e, p, k, s, v, datetime.fromisoformat(a), r)
        for e, p, k, s, v, a, r in conn.execute("SELECT * FROM external_forecasts WHERE entity_id = ?", (entity_id,))
    ]


def save_run(conn: sqlite3.Connection, record: dict, sha256: str | None = None, sealed_at: str | None = None) -> str:
    """Persist a Forecast.to_record() output: one runs row, its latest states and forecasts."""
    run_id = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
        (run_id, record["ticker"], record["as_of"], record["spec_hash"], json.dumps(record["shocks"]),
         record["n_paths"], datetime.now(timezone.utc).isoformat()),
    )
    conn.executemany(
        "INSERT INTO states VALUES (?,?,?,?,?,?,?)",
        [(record["ticker"], record["as_of"], p, prim, s["mean"], s["variance"], run_id)
         for p, by_prim in record["states"].items() for prim, s in by_prim.items()],
    )
    conn.executemany(
        "INSERT INTO forecasts VALUES (?,?,?,?,?,?,?,?,?)",
        [(run_id, k, p, s["p10"], s["p50"], s["p90"], s["mean"], sealed_at, sha256)
         for k, by_p in record["forecast"].items() for p, s in by_p.items()],
    )
    conn.commit()
    return run_id
