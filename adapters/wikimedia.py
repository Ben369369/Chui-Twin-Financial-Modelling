"""Wikimedia Pageviews REST API (daily, per article). Data from July 2015. CC0.

Series: "wiki:<Article_Title>", e.g. "wiki:Chipotle_Mexican_Grill".
Counts human ("user" agent) views on English Wikipedia across all access methods.
available_at: day + 2 (daily dumps land the next day; one day of margin).
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import quote

from adapters.base import Adapter
from adapters.http import PoliteClient, read_raw, save_raw, snapshot_ref
from engine.observation import Observation, RawSnapshot

URL = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
       "{project}/all-access/user/{article}/daily/{start}/{end}")
AVAILABLE_LAG_DAYS = 2
EARLIEST = date(2015, 7, 1)


class WikimediaAdapter(Adapter):
    source = "wikimedia"
    prefix = "wiki"

    def __init__(self, client: PoliteClient | None = None):
        self.client = client or PoliteClient(min_interval_s=1.0)

    def params_for_series(self, series: str) -> dict:
        return {"article": super().params_for_series(series)["query"], "project": "en.wikipedia"}

    def fetch(self, params: dict, start: date, end: date) -> list[RawSnapshot]:
        start = max(start, EARLIEST)
        url = URL.format(project=params.get("project", "en.wikipedia"), article=quote(params["article"], safe=""),
                         start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
        r = self.client.get(url)
        return [save_raw(self.source, r.content, url, dict(params), "json", label=params["article"])]

    def normalize(self, snapshots: list[RawSnapshot]) -> list[Observation]:
        out = []
        for snap in snapshots:
            ref = snapshot_ref(snap)
            for item in json.loads(read_raw(snap)).get("items", []):
                d = datetime.strptime(item["timestamp"][:8], "%Y%m%d").date()
                out.append(Observation(
                    entity_id="macro", source=self.source, series=f"wiki:{item['article']}", observed_at=d,
                    available_at=datetime.combine(d + timedelta(days=AVAILABLE_LAG_DAYS), time(0), timezone.utc),
                    value=float(item["views"]), unit="views", geo=None, source_ref=ref,
                ))
        return out
