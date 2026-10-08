"""Span checks in the ground-truth validator, on wording taken from real earnings releases."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("validate_ground_truth", ROOT / "scripts" / "validate_ground_truth.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def test_span_values_sign_by_clause():
    assert -1.8 in v.span_values("1.8% fewer comparable restaurant transactions")
    both = v.span_values("Comparable restaurant sales for the month of December increased 14.7% "
                         "and declined 4.8% for the full quarter")
    assert 14.7 in both and -4.8 in both
    assert v.span_values("Comparable restaurant sales increased 10.0%") == [10.0]
    assert v.span_values("comparable sales were flat") == [0.0]
