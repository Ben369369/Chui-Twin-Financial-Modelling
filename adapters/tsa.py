"""TSA checkpoint travel numbers (public HTML table, daily, from 2019).

Series: "tsa:checkpoint_throughput".
Current year at /travel/passenger-volumes; past years at /travel/passenger-volumes/<year>.
robots.txt (checked 2026-09-30) disallows only /core/, /profiles/ and README.md.
available_at: day + 2 (TSA posts the prior day's count; one day of margin).
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

from adapters.base import Adapter
from adapters.http import PoliteClient, read_raw, save_raw, snapshot_ref
from engine.observation import Observation, RawSnapshot

BASE = "https://www.tsa.gov/travel/passenger-volumes"
SERIES = "tsa:checkpoint_throughput"
AVAILABLE_LAG_DAYS = 2
FIRST_YEAR = 2019
_ROW = re.compile(r"<td[^>]*>\s*(\d{1,2}/\d{1,2}/\d{4})\s*</td>\s*<td[^>]*>\s*([\d,]+)\s*</td>")


class TsaAdapter(Adapter):
    source = "tsa"
    prefix = "tsa"

    def __init__(self, client: PoliteClient | None = None):
        self.client = client or PoliteClient(min_interval_s=2.0)

    def params_for_series(self, series: str) -> dict:
        if series != SERIES:
            raise ValueError(f"unknown TSA series {series!r}")
        return {}

    def fetch(self, params: dict, start: date, end: date) -> list[RawSnapshot]:
        snaps = []
        this_year = datetime.now(timezone.utc).year
        for y in range(max(start.year, FIRST_YEAR), min(end.year, this_year) + 1):
            url = BASE if y == this_year else f"{BASE}/{y}"
            r = self.client.get(url)
            snaps.append(save_raw(self.source, r.content, url, {"year": y}, "html", label=f"passenger_volumes_{y}"))
        return snaps

    def normalize(self, snapshots: list[RawSnapshot]) -> list[Observation]:
        out: dict[date, Observation] = {}
        for snap in sorted(snapshots, key=lambda s: s.fetched_at):  # later snapshots win
            ref = snapshot_ref(snap)
            for d_text, n_text in _ROW.findall(read_raw(snap).decode("utf-8", errors="replace")):
                d = datetime.strptime(d_text, "%m/%d/%Y").date()
                out[d] = Observation(
                    entity_id="macro", source=self.source, series=SERIES, observed_at=d,
                    available_at=datetime.combine(d + timedelta(days=AVAILABLE_LAG_DAYS), time(0), timezone.utc),
                    value=float(n_text.replace(",", "")), unit="travelers", geo="US", source_ref=ref,
                )
        return sorted(out.values(), key=lambda o: o.observed_at)
