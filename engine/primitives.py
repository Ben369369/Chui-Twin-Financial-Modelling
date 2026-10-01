"""Industry templates: named primitives, default edges, default KPIs.

The engine treats primitive names as opaque strings. All meaning lives in the
template YAML.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class PrimitiveDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    # AR(1) coefficient per period for the standardized state.
    persistence: float = Field(default=0.6, ge=0.0, lt=1.0)


class EdgeDef(BaseModel):
    """Causal edge. Coefficients are in standardized units: a one-sd move in
    the source moves the target by prior_mean target-sd."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source: str = Field(alias="from")
    target: str = Field(alias="to")
    prior_mean: float
    prior_sd: float = Field(gt=0)


class LagPrior(BaseModel):
    """Prior on the coefficient of the KPI's own previous reported value."""

    model_config = ConfigDict(extra="forbid")

    prior_mean: float
    prior_sd: float = Field(gt=0)


class KPIDef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    unit: str
    formula: str | None = None
    # Adds y[t-1] as a regressor. Use for persistent KPIs (year-over-year rates, margins).
    lag: LagPrior | None = None
    description: str = ""

    @model_validator(mode="after")
    def _lag_needs_model(self) -> "KPIDef":
        if self.lag is not None and self.formula:
            raise ValueError("formula KPIs are derived and cannot have a lag term")
        return self


class Template(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    primitives: list[PrimitiveDef]
    edges: list[EdgeDef] = []
    kpis: dict[str, KPIDef] = {}

    @model_validator(mode="after")
    def _unique_primitives(self) -> "Template":
        names = [p.name for p in self.primitives]
        if len(names) != len(set(names)):
            raise ValueError(f"template {self.name}: duplicate primitive names")
        return self

    @property
    def primitive_names(self) -> list[str]:
        return [p.name for p in self.primitives]


def load_template(name: str, templates_dir: str | Path) -> Template:
    path = Path(templates_dir) / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"template {name!r} not found at {path}")
    with open(path, encoding="utf-8") as f:
        return Template.model_validate(yaml.safe_load(f))
