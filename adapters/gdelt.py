"""GDELT 2.0 DOC API: daily news tone and article volume for a search query (from 2017).

Series:
  "gdelt:tone:<query>"  average tone of matching articles (negative = negative coverage)
  "gdelt:vol:<query>"   share of monitored articles that match (attention)
e.g. "gdelt:tone:chipotle". The query is sent as an exact phrase.

GDELT asks for at most one request every 5 seconds. available_at = day + 1.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone

from adapters.base import Adapter
from adapters.http import PoliteClient, read_raw, save_raw, snapshot_ref
from engine.observation import Observation, RawSnapshot

URL = "https://api.gdeltproject.org/api/v2/doc/doc"
MODES = {"tone": "timelinetone", "vol": "timelinevol"}
EARLIEST = date(2017, 1, 1)
AVAILABLE_LAG_DAYS = 1


class GdeltAdapter(Adapter):
    source = "gdelt"
    prefix = "gdelt"

    def __init__(self, client: PoliteClient | None = None):
        # Fail fast on rate limits: run_daily.py fetches any missing series again tomorrow.
        self.client = client or PoliteClient(min_interval_s=6.0, max_retries=1, backoff_s=30.0)

    def params_for_series(self, series: str) -> dict:
        kind, _, query = super().params_for_series(series)["query"].partition(":")
        if kind not in MODES or not query:
            raise ValueError(f"GDELT series must look like gdelt:tone:<query> or gdelt:vol:<query>, got {series!r}")
        return {"kind": kind, "query": query}

    def fetch(self, params: dict, start: date, end: date) -> list[RawSnapshot]:
        start = max(start, EARLIEST)
        q = {"query": f'"{params["query"]}"', "mode": MODES[params["kind"]], "format": "json",
             "startdatetime": start.strftime("%Y%m%d000000"), "enddatetime": end.strftime("%Y%m%d000000")}
        r = self.client.get(URL, params=q)
        if not r.text.lstrip().startswith("{"):
            raise ValueError(f"GDELT returned non-JSON: {r.text[:200]}")
        return [save_raw(self.source, r.content, r.url, dict(params), "json",
                         label=f"{params['kind']}_{params['query']}")]

    def normalize(self, snapshots: list[RawSnapshot]) -> list[Observation]:
        out: dict[tuple[str, date], Observation] = {}
        for snap in sorted(snapshots, key=lambda s: s.fetched_at):
            series = f"gdelt:{snap.params['kind']}:{snap.params['query']}"
            ref = snapshot_ref(snap)
            body = json.loads(read_raw(snap))
            for line in body.get("timeline", [])[:1]:
                for pt in line.get("data", []):
                    d = datetime.strptime(pt["date"][:8], "%Y%m%d").date()
                    out[(series, d)] = Observation(
                        entity_id="macro", source=self.source, series=series, observed_at=d,
                        available_at=datetime.combine(d + timedelta(days=AVAILABLE_LAG_DAYS), time(0), timezone.utc),
                        value=float(pt["value"]), unit="tone" if snap.params["kind"] == "tone" else "pct_articles",
                        geo=None, source_ref=ref,
                    )
        return sorted(out.values(), key=lambda o: (o.series, o.observed_at))
