from pathlib import Path

import pytest
import yaml

from engine.formula import Formula
from engine.periods import bounds, diff, period_of, shift, span
from engine.primitives import load_template
from engine.spec import Spec, load_spec, resolve

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


@pytest.mark.parametrize("name", ["cmg", "dal"])
def test_real_specs_load(name):
    rspec = load_spec(ROOT / "specs" / f"{name}.yaml", TEMPLATES)
    assert rspec.signals and rspec.kpi_edges
    assert len(rspec.spec_hash()) == 64


def _dummy(**overrides) -> Spec:
    base = yaml.safe_load((ROOT / "tests/fixtures/specs/dummy.yaml").read_text(encoding="utf-8"))
    base.update(overrides)
    return Spec.model_validate(base)


def test_rejects_unknown_primitive():
    with pytest.raises(ValueError, match="unknown primitive"):
        resolve(_dummy(signals=[{"series": "x:y", "primitive": "nope", "confidence": 0.5, "half_life_days": 5}]),
                load_template("_dummy", TEMPLATES))


def test_rejects_edge_into_formula_kpi():
    with pytest.raises(ValueError, match="formula KPI"):
        resolve(_dummy(edges=[{"from": "flux_q", "to": "zblx", "prior_mean": 1, "prior_sd": 1}]),
                load_template("_dummy", TEMPLATES))


def test_rejects_primitive_cycle():
    with pytest.raises(ValueError, match="cycle"):
        resolve(_dummy(edges=[{"from": "flux_q", "to": "warp_z", "prior_mean": 1, "prior_sd": 1}]),
                load_template("_dummy", TEMPLATES))


def test_rejects_duplicate_series():
    sig = {"series": "x:y", "primitive": "flux_q", "confidence": 0.5, "half_life_days": 5}
    with pytest.raises(ValueError, match="only once"):
        resolve(_dummy(signals=[sig, sig]), load_template("_dummy", TEMPLATES))


def test_spec_edge_overrides_template_edge():
    rspec = resolve(_dummy(edges=[{"from": "warp_z", "to": "flux_q", "prior_mean": -2, "prior_sd": 1}]),
                    load_template("_dummy", TEMPLATES))
    assert [e.prior_mean for e in rspec.primitive_edges] == [-2]


def test_formula_is_safe_and_differentiable():
    f = Formula("a + 2 * b - c / 4")
    assert f.names == ["a", "b", "c"]
    assert f.evaluate({"a": 1, "b": 2, "c": 4}) == 4
    g = f.gradient({"a": 1, "b": 2, "c": 4})
    assert abs(g["b"] - 2) < 1e-4 and abs(g["c"] + 0.25) < 1e-4
    with pytest.raises(ValueError):
        Formula("__import__('os')")


def test_periods():
    from datetime import date

    assert period_of(date(2024, 11, 3), "quarter") == "2024Q4"
    assert shift("2024Q4", 1) == "2025Q1" and shift("2024-01", -1) == "2023-12"
    assert diff("2025Q2", "2024Q3") == 3
    assert bounds("2024Q1") == (date(2024, 1, 1), date(2024, 3, 31))
    assert bounds("2024-02")[1] == date(2024, 2, 29)
    assert span("2024Q3", "2025Q1") == ["2024Q3", "2024Q4", "2025Q1"]
