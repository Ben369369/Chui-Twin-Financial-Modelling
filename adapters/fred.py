"""FRED (St. Louis Fed) via the key-free fredgraph CSV endpoint.

Series: "fred:<SERIES_ID>", e.g. "fred:RSFSDP".

Point-in-time caveats:
  - fredgraph returns the latest vintage, so historical values may include
    revisions made after as_of. ALFRED vintages (free API key) fix this; see
    docs/model.md. Daily market series (e.g. fuel prices) are not revised.
  - FRED does not give release dates. available_at = end of the period the
    value describes + a conservative release lag chosen by frequency.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from statistics import median

from adapters.base import Adapter
from adapters.http import PoliteClient, read_raw, save_raw, snapshot_ref
from engine.observation import Observation, RawSnapshot

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

# Conservative publication lags, in days after the end of the observed period.
RELEASE_LAG_DAYS = {"daily": 2, "weekly": 7, "monthly": 45, "quarterly": 100}


def _frequency(dates: list[date]) -> str:
    if len(dates) < 3:
        return "monthly"
    gap = median((b - a).days for a, b in zip(dates, dates[1:]))
    if gap <= 4:
        return "daily"
    if gap <= 10:
        return "weekly"
    if gap <= 45:
        return "monthly"
    return "quarterly"


def _period_end(d: date, freq: str) -> date:
    if freq == "monthly":
        nxt = date(d.year + d.month // 12, d.month % 12 + 1, 1)
        return nxt - timedelta(days=1)
    if freq == "quarterly":
        q_end_month = ((d.month - 1) // 3 + 1) * 3
        nxt = date(d.year + q_end_month // 12, q_end_month % 12 + 1, 1)
        return nxt - timedelta(days=1)
    return d


class FredAdapter(Adapter):
    source = "fred"
    prefix = "fred"

    def __init__(self, client: PoliteClient | None = None):
        self.client = client or PoliteClient(min_interval_s=1.0)

    def params_for_series(self, series: str) -> dict:
        return {"series_id": super().params_for_series(series)["query"]}

    def fetch(self, params: dict, start: date, end: date) -> list[RawSnapshot]:
        q = {"id": params["series_id"], "cosd": start.isoformat(), "coed": end.isoformat()}
        r = self.client.get(URL, params=q)
        if not r.text.startswith("observation_date") and not r.text.startswith("DATE"):
            raise ValueError(f"FRED returned non-CSV for {params['series_id']} (unknown series id?)")
        return [save_raw(self.source, r.content, r.url, dict(params), "csv", label=params["series_id"])]

    def normalize(self, snapshots: list[RawSnapshot]) -> list[Observation]:
        out: list[Observation] = []
        for snap in snapshots:
            sid = snap.params["series_id"]
            rows = list(csv.reader(io.StringIO(read_raw(snap).decode("utf-8"))))
            parsed = [(date.fromisoformat(d), v) for d, v in rows[1:] if v not in (".", "")]
            freq = snap.params.get("frequency") or _frequency([d for d, _ in parsed])
            lag = int(snap.params.get("release_lag_days", RELEASE_LAG_DAYS[freq]))
            ref = snapshot_ref(snap)
            for d, v in parsed:
                end = _period_end(d, freq)
                out.append(Observation(
                    entity_id="macro", source=self.source, series=f"fred:{sid}", observed_at=end,
                    available_at=datetime.combine(end + timedelta(days=lag), time(0), timezone.utc),
                    value=float(v), unit=snap.params.get("unit", "index"), geo="US", source_ref=ref,
                ))
        return out
