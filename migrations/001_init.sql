-- Portable SQL: runs on SQLite (dev) and PostgreSQL.
-- Timestamps are ISO-8601 UTC strings; dates are YYYY-MM-DD.

CREATE TABLE IF NOT EXISTS raw_snapshots (
    id          TEXT PRIMARY KEY,          -- sha256 of content
    source      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    path        TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    url         TEXT NOT NULL,
    params      TEXT NOT NULL              -- JSON
);

CREATE TABLE IF NOT EXISTS observations (
    entity_id    TEXT NOT NULL,
    source       TEXT NOT NULL,
    series       TEXT NOT NULL,
    observed_at  TEXT NOT NULL,
    available_at TEXT NOT NULL,
    value        DOUBLE PRECISION NOT NULL,
    unit         TEXT NOT NULL,
    geo          TEXT,
    source_ref   TEXT NOT NULL,
    PRIMARY KEY (entity_id, series, observed_at, available_at)
);
CREATE INDEX IF NOT EXISTS observations_series ON observations (series, available_at);

CREATE TABLE IF NOT EXISTS ground_truth (
    entity_id    TEXT NOT NULL,
    period       TEXT NOT NULL,
    kpi          TEXT NOT NULL,
    value        DOUBLE PRECISION NOT NULL,
    available_at TEXT NOT NULL,
    source_ref   TEXT NOT NULL,
    confidence   DOUBLE PRECISION NOT NULL,
    verified     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (entity_id, period, kpi, available_at)
);

CREATE TABLE IF NOT EXISTS external_forecasts (
    entity_id    TEXT NOT NULL,
    period       TEXT NOT NULL,
    kpi          TEXT NOT NULL,
    source       TEXT NOT NULL,            -- e.g. guidance, consensus
    value        DOUBLE PRECISION NOT NULL,
    available_at TEXT NOT NULL,
    source_ref   TEXT NOT NULL,
    PRIMARY KEY (entity_id, period, kpi, source, available_at)
);

CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    entity_id   TEXT NOT NULL,
    as_of       TEXT NOT NULL,
    spec_hash   TEXT NOT NULL,
    scenario    TEXT NOT NULL,             -- JSON list of shocks
    n_paths     INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS states (
    entity_id  TEXT NOT NULL,
    as_of      TEXT NOT NULL,
    period     TEXT NOT NULL,
    primitive  TEXT NOT NULL,
    mean       DOUBLE PRECISION NOT NULL,
    variance   DOUBLE PRECISION NOT NULL,
    run_id     TEXT NOT NULL REFERENCES runs (id),
    PRIMARY KEY (run_id, period, primitive)
);

CREATE TABLE IF NOT EXISTS forecasts (
    run_id     TEXT NOT NULL REFERENCES runs (id),
    kpi        TEXT NOT NULL,
    period     TEXT NOT NULL,
    p10        DOUBLE PRECISION NOT NULL,
    p50        DOUBLE PRECISION NOT NULL,
    p90        DOUBLE PRECISION NOT NULL,
    mean       DOUBLE PRECISION NOT NULL,
    sealed_at  TEXT,
    sha256     TEXT,
    PRIMARY KEY (run_id, kpi, period)
);
