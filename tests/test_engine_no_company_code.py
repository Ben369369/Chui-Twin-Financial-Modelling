"""Rule 1 guard: engine/ never mentions tickers, primitive names, KPI names or series prefixes."""

import re
from pathlib import Path

import yaml

from adapters import REGISTRY

ROOT = Path(__file__).resolve().parents[1]


def forbidden_words() -> set[str]:
    words: set[str] = set(REGISTRY)
    for path in (ROOT / "specs").glob("*.yaml"):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        words |= {spec["ticker"].lower(), *spec.get("kpis", {})}
        words |= {s["series"].split(":")[0] for s in spec.get("signals", [])}
    for path in (ROOT / "templates").glob("*.yaml"):
        if path.name.startswith("_"):
            continue
        t = yaml.safe_load(path.read_text(encoding="utf-8"))
        words |= {p["name"] for p in t["primitives"]} | set(t.get("kpis", {}))
    return {w.lower() for w in words}


def test_engine_is_company_agnostic():
    words = forbidden_words()
    assert "cmg" in words and "demand" in words  # the guard is actually loaded
    pattern = re.compile(r"\b(" + "|".join(sorted(map(re.escape, words))) + r")\b", re.I)
    hits = []
    for path in (ROOT / "engine").rglob("*.py"):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in pattern.finditer(line):
                hits.append(f"{path.relative_to(ROOT)}:{n}: {m.group(0)!r} in {line.strip()!r}")
    assert not hits, "\n".join(hits)


def test_engine_does_not_import_specs_or_adapters():
    for path in (ROOT / "engine").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+(adapters|specs|storage)\b", text, re.M), path
