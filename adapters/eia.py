"""EIA Open Data API v2, by legacy series id (the id EIA shows on every data page).

Series: "eia:<SERIES_ID>", e.g. "eia:PET.EER_EPJK_PF4_RGC_DPG.D" (US Gulf Coast jet fuel spot, $/gal, daily),
"eia:PET.RWTC.D" (WTI crude spot, $/bbl, daily). The suffix gives the frequency: D, W, M, Q or A.

Key: env CHUI_EIA_API_KEY (free, eia.gov/opendata/register.php). Without it the adapter uses api.data.gov's
public DEMO_KEY, which is meant for trying the API (about 10 requests an hour) and prints a warning.
The key is sent as a query parameter, so saved URLs and error messages are built without it.

The /v2/seriesid endpoint ignores start and end and returns rows newest first, 5,000 per page, so a fetch
pages back until it passes `start`. A daily run is one request per series.

available_at: EIA spot prices are published with a short delay; we use the same conservative lags as the
FRED copies these replace: period end + 2 days (daily), 7 (weekly), 45 (monthly), 100 (quarterly), 120 (annual).
Market prices are not revised in practice.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlencode

from adapters.base import Adapter
from adapters.http import PoliteClient, read_raw, save_raw, snapshot_ref
from engine.observation import Observation, RawSnapshot

URL = "https://api.eia.gov/v2/seriesid/{sid}"
KEY_ENV = "CHUI_EIA_API_KEY"
DEMO_KEY = "DEMO_KEY"
PAGE = 5000
FREQ = {"D": "daily", "W": "weekly", "M": "monthly", "Q": "quarterly", "A": "annual"}
RELEASE_LAG_DAYS = {"daily": 2, "weekly": 7, "monthly": 45, "quarterly": 100, "annual": 120}
ROWS_PER_DAY = {"daily": 1.0, "weekly": 1 / 7, "monthly": 1 / 28, "quarterly": 1 / 90, "annual": 1 / 365}


def _frequency(sid: str) -> str:
    suffix = sid.rsplit(".", 1)[-1].upper()
    if suffix not in FREQ:
        raise ValueError(f"EIA series id {sid!r} must end in .D, .W, .M, .Q or .A")
    return FREQ[suffix]


def _period_end(period: str, freq: str) -> date:
    if freq in ("daily", "weekly"):
        return date.fromisoformat(period[:10])
    y = int(period[:4])
    if freq == "annual":
        return date(y, 12, 31)
    m = int(period[6:]) * 3 if freq == "quarterly" else int(period[5:7])  # "2026-Q3" or "2026-09"
    return date(y + m // 12, m % 12 + 1, 1) - timedelta(days=1)


class EiaAdapter(Adapter):
    source = "eia"
    prefix = "eia"

    def __init__(self, client: PoliteClient | None = None):
        self.client = client or PoliteClient(min_interval_s=1.0, max_retries=2)
        self.key = os.environ.get(KEY_ENV) or None

    def params_for_series(self, series: str) -> dict:
        sid = super().params_for_series(series)["query"]
        _frequency(sid)
        return {"series_id": sid}

    def fetch(self, params: dict, start: date, end: date) -> list[RawSnapshot]:
        sid = params["series_id"]
        freq = _frequency(sid)
        if not self.key:
            print(f"  eia: {KEY_ENV} not set; using the public DEMO_KEY (for trying the API only)")
        key = self.key or DEMO_KEY
        # Enough rows to reach back to `start` in one page when possible.
        length = min(PAGE, int((date.today() - start).days * ROWS_PER_DAY[freq]) + 10)
        snaps, offset = [], 0
        while True:
            q = {"length": length, "offset": offset}
            url = f"{URL.format(sid=sid)}?{urlencode(q)}"  # saved and shown without the key
            try:
                r = self.client.get(URL.format(sid=sid), params=q | {"api_key": key})
            except Exception as e:
                raise RuntimeError(str(e).replace(key, "***")) from None
            if key.encode() in r.content:
                raise RuntimeError(f"EIA response for {sid} echoes the API key; not saved")
            reply = r.json()
            if "error" in reply or "response" not in reply:
                raise ValueError(f"EIA error for {sid}: {reply.get('error') or reply}")
            snaps.append(save_raw(self.source, r.content, url, dict(params) | q, "json",
                                  label=f"{sid}_{offset}"))
            rows = reply["response"].get("data", [])
            oldest = min((_period_end(str(x["period"]), freq) for x in rows), default=None)
            offset += len(rows)
            if not rows or len(rows) < length or oldest is None or oldest <= start:
                return snaps
            length = PAGE

    def normalize(self, snapshots: list[RawSnapshot]) -> list[Observation]:
        out: dict[tuple[str, date], Observation] = {}
        for snap in sorted(snapshots, key=lambda s: s.fetched_at):
            sid = snap.params["series_id"]
            freq = _frequency(sid)
            lag = RELEASE_LAG_DAYS[freq]
            ref = snapshot_ref(snap)
            for row in json.loads(read_raw(snap))["response"].get("data", []):
                try:
                    value = float(row["value"])
                except (TypeError, ValueError):  # null or "NA"
                    continue
                end = _period_end(str(row["period"]), freq)
                out[(sid, end)] = Observation(
                    entity_id="macro", source=self.source, series=f"eia:{sid}", observed_at=end,
                    available_at=datetime.combine(end + timedelta(days=lag), time(0), timezone.utc),
                    value=value, unit=row.get("units") or "value", geo=row.get("duoarea"), source_ref=ref,
                )
        return list(out.values())
