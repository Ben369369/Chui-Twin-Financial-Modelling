"""Adapter registry: series prefix -> adapter class."""

from __future__ import annotations

from pathlib import Path

import yaml

from adapters.base import Adapter
from adapters.bls import BlsAdapter
from adapters.eia import EiaAdapter
from adapters.fred import FredAdapter
from adapters.gdelt import GdeltAdapter
from adapters.scrapers.sitemap import SitemapAdapter
from adapters.tsa import TsaAdapter
from adapters.wikimedia import WikimediaAdapter

REGISTRY: dict[str, type[Adapter]] = {
    cls.prefix: cls
    for cls in (FredAdapter, BlsAdapter, EiaAdapter, WikimediaAdapter, TsaAdapter, SitemapAdapter, GdeltAdapter)
}


def adapter_for(series: str) -> Adapter:
    prefix = series.partition(":")[0]
    if prefix not in REGISTRY:
        raise KeyError(f"no adapter for series prefix {prefix!r} (known: {sorted(REGISTRY)})")
    return REGISTRY[prefix]()


def batches(series: list[str]) -> list[tuple[Adapter, list[str]]]:
    """Group series that one adapter can fetch together (fetch_many), in the given order.
    Adapters without multi-series requests get one series per group."""
    groups: dict[str, tuple[Adapter, list[str]]] = {}
    out: list[tuple[Adapter, list[str]]] = []
    for name in series:
        prefix = name.partition(":")[0]
        if prefix in groups and len(groups[prefix][1]) < groups[prefix][0].batch_size:
            groups[prefix][1].append(name)
            continue
        group = (adapter_for(name), [name])
        out.append(group)
        if group[0].batch_size > 1:
            groups[prefix] = group
    return out


def moved_series() -> dict[str, str]:
    """Old series name -> its replacement (adapters/series_moves.yaml)."""
    return yaml.safe_load((Path(__file__).with_name("series_moves.yaml")).read_text(encoding="utf-8")) or {}
