"""BLS Public Data API v2, used without a registration key (25 queries/day, 10 years per query).

Series: "bls:<SERIES_ID>", e.g. "bls:CES7072200003" (avg hourly earnings, food services).

available_at: BLS does not return release dates here. CES data for month M is
released on the first Friday of M+1 or M+2; we use period end + 40 days,
which is conservative. Preliminary values are revised twice; the API returns
the latest vintage (same caveat as FRED).
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone

from adapters.base import Adapter
from adapters.http import PoliteClient, read_raw, save_raw, snapshot_ref
from engine.observation import Observation, RawSnapshot

URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/{sid}"
MONTHLY_RELEASE_LAG_DAYS = 40
MAX_YEARS_PER_QUERY = 10


class BlsAdapter(Adapter):
    source = "bls"
    prefix = "bls"

    def __init__(self, client: PoliteClient | None = None):
        self.client = client or PoliteClient(min_interval_s=2.0)

    def params_for_series(self, series: str) -> dict:
        return {"series_id": super().params_for_series(series)["query"]}

    def fetch(self, params: dict, start: date, end: date) -> list[RawSnapshot]:
        sid, snaps = params["series_id"], []
        y = start.year
        while y <= end.year:
            y2 = min(end.year, y + MAX_YEARS_PER_QUERY - 1)
            r = self.client.get(URL.format(sid=sid), params={"startyear": y, "endyear": y2})
            body = r.json()
            if body.get("status") != "REQUEST_SUCCEEDED":
                raise ValueError(f"BLS error for {sid}: {body.get('message')}")
            snaps.append(save_raw(self.source, r.content, r.url, dict(params), "json", label=f"{sid}_{y}_{y2}"))
            y = y2 + 1
        return snaps

    def normalize(self, snapshots: list[RawSnapshot]) -> list[Observation]:
        out: dict[tuple[str, date], Observation] = {}
        for snap in sorted(snapshots, key=lambda s: s.fetched_at):
            ref = snapshot_ref(snap)
            for s in json.loads(read_raw(snap))["Results"]["series"]:
                for row in s["data"]:
                    if not row["period"].startswith("M") or row["period"] == "M13" or row["value"] in ("-", ""):
                        continue
                    y, m = int(row["year"]), int(row["period"][1:])
                    end = date(y + m // 12, m % 12 + 1, 1) - timedelta(days=1)
                    out[(s["seriesID"], end)] = Observation(
                        entity_id="macro", source=self.source, series=f"bls:{s['seriesID']}", observed_at=end,
                        available_at=datetime.combine(end + timedelta(days=MONTHLY_RELEASE_LAG_DAYS), time(0), timezone.utc),
                        value=float(row["value"]), unit=snap.params.get("unit", "index"), geo="US", source_ref=ref,
                    )
        return list(out.values())
