"""Core data records shared by adapters, storage and the engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Iterable, Protocol, TypeVar


def as_utc(ts: datetime) -> datetime:
    """Treat naive datetimes as UTC so comparisons never mix aware and naive."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


@dataclass(frozen=True)
class RawSnapshot:
    source: str
    fetched_at: datetime
    path: str
    sha256: str
    params: dict = field(default_factory=dict)
    url: str = ""


@dataclass(frozen=True)
class Observation:
    entity_id: str
    source: str
    series: str
    observed_at: date
    available_at: datetime
    value: float
    unit: str
    geo: str | None
    source_ref: str


@dataclass(frozen=True)
class GroundTruth:
    """A reported KPI value for one period."""

    entity_id: str
    period: str
    kpi: str
    value: float
    available_at: datetime
    source_ref: str
    confidence: float = 1.0
    verified: bool = False


@dataclass(frozen=True)
class ExternalForecast:
    """A point forecast made by someone else (management guidance, consensus)."""

    entity_id: str
    period: str
    kpi: str
    source: str
    value: float
    available_at: datetime
    source_ref: str


class _HasAvailableAt(Protocol):
    available_at: datetime


T = TypeVar("T", bound=_HasAvailableAt)


def available_as_of(rows: Iterable[T], as_of: datetime) -> list[T]:
    """Point-in-time filter. The only sanctioned way to cut data for a backtest."""
    cutoff = as_utc(as_of)
    return [r for r in rows if as_utc(r.available_at) <= cutoff]
