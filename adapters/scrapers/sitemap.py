"""Count URLs in public sitemaps: store locators (capacity), careers sites (hiring).

Series: "sitemap:<name>", configured in adapters/scrapers/sitemaps.yaml.

Live fetch reads today's sitemaps. History comes from the Internet Archive's
Wayback Machine: one capture per month from the CDX index, fetched with the
"id_" flag (original bytes). A capture counts only if every child sitemap of an
index resolves within MAX_CHILD_SKEW_DAYS of the parent.

observed_at = capture date; available_at = capture time, since the sitemap was
publicly readable then. Polite: 2 s between requests, descriptive User-Agent.
"""

from __future__ import annotations

import gzip
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from adapters.base import Adapter
from adapters.http import PoliteClient, read_raw, save_raw, snapshot_ref
from engine.observation import Observation, RawSnapshot

CONFIG = Path(__file__).with_name("sitemaps.yaml")
CDX = "https://web.archive.org/cdx/search/cdx"
WAYBACK = "https://web.archive.org/web/{ts}id_/{url}"
MAX_CHILD_SKEW_DAYS = 20
LIVE_WINDOW_DAYS = 2
_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_TS = re.compile(r"/web/(\d{14})")


def load_config() -> dict[str, dict]:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def _xml(raw: bytes) -> str:
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", errors="replace")


def _is_index(text: str) -> bool:
    return "<sitemapindex" in text[:2000]


class SitemapAdapter(Adapter):
    source = "sitemap"
    prefix = "sitemap"

    def __init__(self, client: PoliteClient | None = None, config: dict | None = None):
        self.client = client or PoliteClient(min_interval_s=2.0)
        self.config = config if config is not None else load_config()

    def params_for_series(self, series: str) -> dict:
        name = super().params_for_series(series)["query"]
        if name not in self.config:
            raise ValueError(f"no sitemap config named {name!r} in {CONFIG.name}")
        return {"name": name}

    # ---- fetching -------------------------------------------------------

    def _get_tree(self, url: str, group: str, name: str, ts: str | None) -> list[RawSnapshot]:
        """Fetch a sitemap (live, or a Wayback capture) and its children if it is an index."""
        fetch_url = WAYBACK.format(ts=ts, url=url) if ts else url
        r = self.client.get(fetch_url)
        captured = _TS.search(r.url).group(1) if ts and _TS.search(r.url) else ts
        params = {"name": name, "group": group, "url": url, "captured": captured}
        snaps = [save_raw(self.source, r.content, fetch_url, params, "xml", label=f"{name}_{group}_{url}")]
        text = _xml(r.content)
        if _is_index(text):
            for child in _LOC.findall(text):
                snaps += self._get_tree(child, group, name, ts)
        return snaps

    def _captures(self, url: str, start: date, end: date) -> list[str]:
        r = self.client.get(CDX, params={"url": url, "output": "json", "fl": "timestamp,statuscode",
                                         "from": start.strftime("%Y%m%d"), "to": end.strftime("%Y%m%d"),
                                         "collapse": "timestamp:6", "filter": "statuscode:200"})
        rows = r.json()[1:] if r.text.strip() else []
        return [ts for ts, _ in rows]

    def fetch(self, params: dict, start: date, end: date) -> list[RawSnapshot]:
        cfg = self.config[params["name"]]
        today = datetime.now(timezone.utc).date()
        snaps: list[RawSnapshot] = []
        if start < today - timedelta(days=LIVE_WINDOW_DAYS):
            for url in cfg["sitemaps"]:
                for ts in self._captures(url, start, min(end, today)):
                    snaps += self._get_tree(url, f"wayback-{ts}", params["name"], ts)
        if end >= today - timedelta(days=LIVE_WINDOW_DAYS):
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            for url in cfg["sitemaps"]:
                snaps += self._get_tree(url, f"live-{stamp}", params["name"], None)
        return snaps

    # ---- parsing --------------------------------------------------------

    def normalize(self, snapshots: list[RawSnapshot]) -> list[Observation]:
        groups: dict[tuple[str, str], list[RawSnapshot]] = defaultdict(list)
        for s in snapshots:
            groups[(s.params["name"], s.params["group"])].append(s)
        out: dict[tuple[str, date], Observation] = {}
        for (name, group), snaps in sorted(groups.items()):
            cfg = self.config[name]
            pattern = re.compile(cfg["count_pattern"])
            if group.startswith("wayback-"):
                parent = datetime.strptime(group[8:], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                stamps = [datetime.strptime(s.params["captured"], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                          for s in snaps if s.params.get("captured")]
                if any(abs((t - parent).days) > MAX_CHILD_SKEW_DAYS for t in stamps):
                    continue  # children captured too far from the parent: not one coherent snapshot
                when = max(stamps) if stamps else parent
            else:
                when = min(s.fetched_at for s in snaps)
            urls: set[str] = set()
            for s in snaps:
                urls |= {u for u in _LOC.findall(_xml(read_raw(s))) if pattern.search(u)}
            if len(urls) < cfg.get("min_valid", 1):
                continue  # empty or truncated listing
            obs = Observation(
                entity_id=cfg.get("entity_id", "macro"), source=self.source, series=f"sitemap:{name}",
                observed_at=when.date(), available_at=when, value=float(len(urls)), unit=cfg.get("unit", "urls"),
                geo=None, source_ref=" + ".join(snapshot_ref(s) for s in snaps[:3]) + (" ..." if len(snaps) > 3 else ""),
            )
            out[(name, when.date())] = obs
        return sorted(out.values(), key=lambda o: o.observed_at)
