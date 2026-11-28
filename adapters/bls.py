"""BLS Public Data API v2: CPI, average prices, PPI, employment and earnings, many series per request.

Series: "bls:<SERIES_ID>", e.g. "bls:CES7072200003" (avg hourly earnings, food services),
"bls:CUSR0000SEFV" (CPI food away from home), "bls:APU0000703112" (ground beef, per lb).

Registration key: env CHUI_BLS_API_KEY, optional. Without it: 25 queries a day, 25 series and 10 years
per query. With it: 500 queries a day, 50 series and 20 years per query. The key goes in the POST body,
never in a URL or a saved file. fetch_many combines series, so the daily job spends one query, not one
per series.

available_at: BLS does not return release dates here. CPI, average prices and PPI for month M come out
mid M+1; CES earnings on the first Friday of M+1 or M+2. We use period end + 40 days, which is
conservative for all of them. Preliminary values are revised; the API returns the latest vintage.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta, timezone

from adapters.base import Adapter
from adapters.http import PoliteClient, read_raw, save_raw, snapshot_ref
from engine.observation import Observation, RawSnapshot

URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
KEY_ENV = "CHUI_BLS_API_KEY"
MONTHLY_RELEASE_LAG_DAYS = 40


def _limits(keyed: bool) -> tuple[int, int]:
    """(series per query, years per query)."""
    return (50, 20) if keyed else (25, 10)


class BlsAdapter(Adapter):
    source = "bls"
    prefix = "bls"

    def __init__(self, client: PoliteClient | None = None):
        self.client = client or PoliteClient(min_interval_s=2.0)
        self.key = os.environ.get(KEY_ENV) or None
        self.batch_size = _limits(bool(self.key))[0]

    def params_for_series(self, series: str) -> dict:
        return {"series_id": super().params_for_series(series)["query"]}

    def fetch(self, params: dict, start: date, end: date) -> list[RawSnapshot]:
        return self._fetch_ids([params["series_id"]], start, end)

    def fetch_many(self, series: list[str], start: date, end: date) -> list[RawSnapshot]:
        ids = [self.params_for_series(s)["series_id"] for s in series]
        return [s for i in range(0, len(ids), self.batch_size)
                for s in self._fetch_ids(ids[i:i + self.batch_size], start, end)]

    def _fetch_ids(self, ids: list[str], start: date, end: date) -> list[RawSnapshot]:
        years = _limits(bool(self.key))[1]
        snaps, y = [], start.year
        while y <= end.year:
            y2 = min(end.year, y + years - 1)
            body = {"seriesid": ids, "startyear": str(y), "endyear": str(y2)}
            r = self.client.post(URL, json=body | ({"registrationkey": self.key} if self.key else {}))
            reply = r.json()
            if reply.get("status") != "REQUEST_SUCCEEDED":
                raise ValueError(f"BLS error for {ids}: {reply.get('message')}")
            label = ids[0] if len(ids) == 1 else f"{len(ids)}series_{ids[0]}"
            params = {"series_ids": ids, "startyear": y, "endyear": y2}
            if len(ids) == 1:
                params["series_id"] = ids[0]
            snaps.append(save_raw(self.source, r.content, URL, params, "json", label=f"{label}_{y}_{y2}"))
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
