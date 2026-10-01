"""Adapter registry: series prefix -> adapter class."""

from __future__ import annotations

from adapters.base import Adapter
from adapters.bls import BlsAdapter
from adapters.fred import FredAdapter
from adapters.tsa import TsaAdapter
from adapters.wikimedia import WikimediaAdapter

REGISTRY: dict[str, type[Adapter]] = {
    cls.prefix: cls for cls in (FredAdapter, BlsAdapter, WikimediaAdapter, TsaAdapter)
}


def adapter_for(series: str) -> Adapter:
    prefix = series.partition(":")[0]
    if prefix not in REGISTRY:
        raise KeyError(f"no adapter for series prefix {prefix!r} (known: {sorted(REGISTRY)})")
    return REGISTRY[prefix]()
