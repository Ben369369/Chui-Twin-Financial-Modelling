"""Industry templates: named primitives, default edges, default KPIs.

The engine treats primitive names as opaque strings. All meaning lives in the
template YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

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
    # Adds y[t - one year] as a regressor. Use for seasonal levels (e.g. quarterly margins).
    seasonal_lag: LagPrior | None = None
    # "change": model y[t] - y[t-1] from changes in parent states since the last period.
    # Suits year-over-year KPIs, where the news since the last report is in the signal changes.
    target: Literal["level", "change"] = "level"
    # For target: change, what the change is measured from: the last reported value, or an
    # external forecast source (e.g. "guidance"), falling back to the last reported value
    # for periods without one. Anchoring on guidance models the surprise versus guidance.
    anchor: str = "last_reported"
    # Hard operating limits [low, high] (either may be null). Simulated paths are clipped to them,
    # e.g. a margin cannot exceed 100% and revenue cannot fall more than 100%.
    bounds: tuple[float | None, float | None] | None = None
    description: str = ""

    @model_validator(mode="after")
    def _lag_needs_model(self) -> "KPIDef":
        if (self.lag is not None or self.seasonal_lag is not None) and self.formula:
            raise ValueError("formula KPIs are derived and cannot have lag terms")
        if self.target == "change" and (self.formula or self.lag is not None or self.seasonal_lag is not None):
            raise ValueError("target: change already conditions on y[t-1]; it excludes formula and lag terms")
        if self.anchor != "last_reported" and self.target != "change":
            raise ValueError("anchor applies only to target: change")
        if self.bounds is not None:
            lo, hi = self.bounds
            if lo is not None and hi is not None and lo >= hi:
                raise ValueError(f"bounds must satisfy low < high, got {self.bounds}")
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
