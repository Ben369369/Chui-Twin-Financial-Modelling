"""Company specs: load, merge with the chosen template, validate.

A spec picks a template, selects a subset of its primitives, declares KPIs,
maps data series to primitives, and adds or overrides causal edges.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from engine.formula import Formula
from engine.periods import FREQUENCIES, span
from engine.primitives import EdgeDef, KPIDef, PrimitiveDef, Template, load_template

BUILTIN_BASELINES = ("naive_last", "seasonal_naive")


class SignalSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: str
    primitive: str
    sign: Literal[-1, 1] = 1
    lag_days: int = Field(default=0, ge=0)
    # Probability-like trust in the signal as a sensor of the primitive.
    # Mapped to measurement noise variance (1 - c) / c. See docs/model.md.
    confidence: float = Field(gt=0.0, lt=1.0)
    half_life_days: float = Field(gt=0)
    # How raw values become a per-period feature before standardization.
    transform: Literal["yoy_log", "yoy_diff", "level"] = "yoy_log"
    # Restrict to one entity; default accepts the spec's ticker or "macro".
    entity_id: str | None = None
    notes: str = ""


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    name: str
    template: str
    industry: str = ""
    period: str = "quarter"
    # First period used for state estimation and standardization.
    history_start: str | None = None
    # Periods (or "first:last" ranges) left out of KPI calibration, e.g. a regime break.
    # Stated in the spec so the choice is visible; they are still forecast and scored.
    exclude_from_calibration: list[str] = []
    kpis: dict[str, KPIDef] = {}
    primitives: list[str] | None = None
    persistence: dict[str, float] = {}
    signals: list[SignalSpec] = []
    edges: list[EdgeDef] = []
    baselines: list[str] = list(BUILTIN_BASELINES)
    # Free-form config used by ingestion scripts (e.g. filing extraction rules).
    # The engine never reads it.
    ground_truth: dict = {}
    notes: str = ""


@dataclass
class ResolvedSpec:
    ticker: str
    name: str
    template: str
    period: str
    primitives: list[PrimitiveDef]
    kpis: dict[str, KPIDef]
    signals: list[SignalSpec]
    primitive_edges: list[EdgeDef]  # primitive -> primitive
    kpi_edges: list[EdgeDef]  # primitive -> KPI
    baselines: list[str]
    ground_truth: dict
    history_start: str | None = None
    excluded_periods: set[str] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)

    @property
    def primitive_names(self) -> list[str]:
        return [p.name for p in self.primitives]

    @property
    def formulas(self) -> dict[str, Formula]:
        return {k: Formula(d.formula) for k, d in self.kpis.items() if d.formula}

    @property
    def modeled_kpis(self) -> list[str]:
        """KPIs estimated from primitives (not derived by formula)."""
        return [k for k, d in self.kpis.items() if not d.formula]

    def kpi_order(self) -> list[str]:
        """Modeled KPIs first, then formula KPIs in dependency order."""
        order = list(self.modeled_kpis)
        pending = dict(self.formulas)
        while pending:
            ready = [k for k, f in pending.items() if all(n in order for n in f.names)]
            if not ready:
                raise ValueError(f"cyclic KPI formulas: {sorted(pending)}")
            for k in sorted(ready):
                order.append(k)
                del pending[k]
        return order

    def primitive_order(self) -> list[str]:
        """Topological order of primitives under primitive->primitive edges."""
        names = self.primitive_names
        parents = {n: {e.source for e in self.primitive_edges if e.target == n} for n in names}
        order: list[str] = []
        while len(order) < len(names):
            ready = [n for n in names if n not in order and parents[n] <= set(order)]
            if not ready:
                raise ValueError("primitive edges contain a cycle")
            order.extend(ready)
        return order

    def spec_hash(self) -> str:
        payload = {
            "ticker": self.ticker,
            "template": self.template,
            "period": self.period,
            "history_start": self.history_start,
            "excluded_periods": sorted(self.excluded_periods),
            "primitives": [p.model_dump() for p in self.primitives],
            "kpis": {k: v.model_dump() for k, v in sorted(self.kpis.items())},
            "signals": [s.model_dump() for s in self.signals],
            "edges": [e.model_dump() for e in self.primitive_edges + self.kpi_edges],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _expand_periods(items: list[str]) -> set[str]:
    out: set[str] = set()
    for item in items:
        first, _, last = item.partition(":")
        out |= set(span(first, last or first))
    return out


def resolve(spec: Spec, template: Template) -> ResolvedSpec:
    notes: list[str] = []
    if spec.template != template.name:
        raise ValueError(f"spec wants template {spec.template!r}, got {template.name!r}")
    if spec.period not in FREQUENCIES:
        raise ValueError(f"period must be one of {FREQUENCIES}")

    by_name = {p.name: p for p in template.primitives}
    chosen = spec.primitives if spec.primitives is not None else template.primitive_names
    unknown = [p for p in chosen if p not in by_name]
    if unknown:
        raise ValueError(f"primitives {unknown} are not in template {template.name!r}")
    primitives = []
    for name in chosen:
        p = by_name[name]
        if name in spec.persistence:
            p = p.model_copy(update={"persistence": spec.persistence[name]})
        primitives.append(p)
    for name in spec.persistence:
        if name not in chosen:
            raise ValueError(f"persistence override for unused primitive {name!r}")

    kpis = dict(spec.kpis) if spec.kpis else dict(template.kpis)
    if not kpis:
        raise ValueError("spec defines no KPIs and the template has no defaults")
    prim_set, kpi_set = set(chosen), set(kpis)
    overlap = prim_set & kpi_set
    if overlap:
        raise ValueError(f"names used as both primitive and KPI: {sorted(overlap)}")

    for k, d in kpis.items():
        if d.formula:
            missing = [n for n in Formula(d.formula).names if n not in kpi_set]
            if missing:
                raise ValueError(f"KPI {k!r} formula references unknown KPIs {missing}")

    for s in spec.signals:
        if s.primitive not in prim_set:
            raise ValueError(f"signal {s.series!r} maps to unknown primitive {s.primitive!r}")
    seen = [s.series for s in spec.signals]
    if len(seen) != len(set(seen)):
        raise ValueError("a series may be mapped only once per spec")

    # Merge edges: spec overrides template on the same (source, target).
    merged: dict[tuple[str, str], EdgeDef] = {}
    nodes = prim_set | kpi_set
    for e in template.edges:
        if e.source in nodes and e.target in nodes:
            merged[(e.source, e.target)] = e
        else:
            notes.append(f"template edge {e.source}->{e.target} dropped: endpoint not in spec")
    for e in spec.edges:
        if e.source not in nodes or e.target not in nodes:
            raise ValueError(f"edge {e.source}->{e.target} references an unknown node")
        merged[(e.source, e.target)] = e

    formula_kpis = {k for k, d in kpis.items() if d.formula}
    primitive_edges, kpi_edges = [], []
    for e in merged.values():
        if e.source in kpi_set:
            raise ValueError(f"edge {e.source}->{e.target}: KPIs cannot be edge sources; use a formula")
        if e.target in formula_kpis:
            raise ValueError(f"edge into formula KPI {e.target!r}; formula KPIs are derived")
        (kpi_edges if e.target in kpi_set else primitive_edges).append(e)

    for k in kpis:
        if k not in formula_kpis and not any(e.target == k for e in kpi_edges):
            notes.append(f"KPI {k!r} has no driver edges; it will be forecast by its intercept only")

    for b in spec.baselines:
        if b not in BUILTIN_BASELINES:
            notes.append(f"baseline {b!r} is external; supply ExternalForecast rows with source={b!r}")

    resolved = ResolvedSpec(
        ticker=spec.ticker,
        name=spec.name,
        template=template.name,
        period=spec.period,
        primitives=primitives,
        kpis=kpis,
        signals=list(spec.signals),
        primitive_edges=primitive_edges,
        kpi_edges=kpi_edges,
        baselines=list(spec.baselines),
        ground_truth=dict(spec.ground_truth),
        history_start=spec.history_start,
        excluded_periods=_expand_periods(spec.exclude_from_calibration),
        notes=notes,
    )
    resolved.primitive_order()  # raises on cycles
    resolved.kpi_order()
    return resolved


def load_spec(path: str | Path, templates_dir: str | Path) -> ResolvedSpec:
    with open(path, encoding="utf-8") as f:
        spec = Spec.model_validate(yaml.safe_load(f))
    return resolve(spec, load_template(spec.template, templates_dir))
