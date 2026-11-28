"""Adapter interface. Adapters fetch and normalize; they know nothing about states or companies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from engine.observation import Observation, RawSnapshot

__all__ = ["Adapter", "Observation", "RawSnapshot"]


class Adapter(ABC):
    source: str
    # Series names look like "<prefix>:<query>"; the registry routes by prefix.
    prefix: str

    @abstractmethod
    def fetch(self, params: dict, start: date, end: date) -> list[RawSnapshot]: ...

    @abstractmethod
    def normalize(self, snapshots: list[RawSnapshot]) -> list[Observation]: ...

    # How many series one fetch_many call may combine (sources with multi-series requests override).
    batch_size: int = 1

    def fetch_many(self, series: list[str], start: date, end: date) -> list[RawSnapshot]:
        """Fetch several series of this adapter. Sources whose API takes many series per request override
        this to save requests; the default fetches one at a time."""
        return [s for name in series for s in self.fetch(self.params_for_series(name), start, end)]

    def params_for_series(self, series: str) -> dict:
        """Turn a series name into fetch params. Override when the query needs parsing."""
        prefix, _, query = series.partition(":")
        if prefix != self.prefix or not query:
            raise ValueError(f"{self.source} cannot serve series {series!r}")
        return {"query": query}
