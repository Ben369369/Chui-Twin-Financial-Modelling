"""LLM onboarding checks: no network, no model call. A hand-written draft stands in for the model's reply."""

from pathlib import Path

import yaml

from engine.primitives import load_template
from engine.spec import load_spec
from onboarding.factory import load_packs
from onboarding.llm import Draft, apply, check, fit_text, output_schema, quote_found, _norm

ROOT = Path(__file__).resolve().parents[1]
TEXT = ("Item 1. Business. We operate a fleet of 90 ships. Fuel is our largest single operating expense and "
        "a 10% change in fuel prices would change our fuel expense by about $200 million. Demand for cruise "
        "vacations is affected by consumer confidence and discretionary spending. We report net yields, "
        "which we define as net revenue per available lower berth day.")

DRAFT = {
    "business_summary": "Cruise operator.",
    "pack": {"pack": "airlines", "reason": "travel demand and fuel",
             "quote": "Fuel is our largest single operating expense"},
    "drivers": [
        # accepted: known series, quote verbatim (with curly apostrophes and different spacing)
        {"series": "fred:CPILFESL", "state": "price", "sign": 1, "lag_days": 0, "transform": "yoy_log",
         "strength": "weak", "reason": "pricing", "quote": "Demand for  cruise vacations is affected by consumer confidence"},
        # rejected: paraphrased quote
        {"series": "fred:RSGMS", "state": "demand", "sign": 1, "lag_days": 0, "transform": "yoy_log",
         "strength": "weak", "reason": "spending", "quote": "Cruise demand depends heavily on how consumers feel"},
        # rejected: unknown state
        {"series": "fred:HOUST", "state": "weather", "sign": 1, "lag_days": 0, "transform": "yoy_log",
         "strength": "weak", "reason": "x", "quote": "Demand for cruise vacations is affected by consumer confidence"},
        # rejected: already in the pack
        {"series": "fred:DJFUELUSGULF", "state": "input_cost", "sign": 1, "lag_days": 0, "transform": "yoy_log",
         "strength": "moderate", "reason": "fuel", "quote": "Fuel is our largest single operating expense"},
        # new FRED id: goes to series_ok
        {"series": "fred:NEWID", "state": "input_cost", "sign": 1, "lag_days": 0, "transform": "yoy_log",
         "strength": "moderate", "reason": "fuel", "quote": "a 10% change in fuel prices would change our fuel expense"},
    ],
    "kpis": [
        {"name": "fuel_share", "kind": "ratio", "concepts": ["FuelCosts"], "description": "fuel % of revenue",
         "reason": "largest cost", "quote": "Fuel is our largest single operating expense"},
        {"name": "Bad Name", "kind": "yoy", "concepts": ["X"], "description": "", "reason": "",
         "quote": "Fuel is our largest single operating expense"},
    ],
    "edges": [
        {"state": "input_cost", "kpi": "fuel_share", "prior_mean": 1.7, "reason": "fuel",
         "quote": "Fuel is our largest single operating expense"},
        {"state": "demand", "kpi": "revenue_growth", "prior_mean": 0.8, "reason": "demand",
         "quote": "Demand for cruise vacations is affected by consumer confidence"},
        {"state": "demand", "kpi": "no_such_kpi", "prior_mean": 0.5, "reason": "",
         "quote": "Demand for cruise vacations is affected by consumer confidence"},
    ],
    "operating_kpis": [
        {"name": "net_yields", "definition": "net revenue per berth day",
         "quote": "which we define as net revenue per available lower berth day"},
    ],
}


def run_check(series_ok=lambda s: None, kpi_ok=lambda k: None):
    packs = load_packs()
    template = load_template("operating", ROOT / "templates")
    return check(Draft.model_validate(DRAFT), TEXT, packs=packs, primitives={p.name for p in template.primitives},
                 known_series={"fred:CPILFESL", "fred:RSGMS", "fred:HOUST", "fred:DJFUELUSGULF"},
                 default_kpis=set(packs["defaults"]["kpis"]),
                 pack_series=lambda name: {s["series"] for s in packs["packs"][name]["signals"]} if name else set(),
                 series_ok=series_ok, kpi_ok=kpi_ok)


def test_quotes_must_be_verbatim():
    t = _norm(TEXT)
    assert quote_found("Fuel is our largest single operating expense.", t)
    assert quote_found("FUEL is our  largest single\noperating expense", t)  # case and whitespace only
    assert not quote_found("Fuel is our biggest single operating expense", t)
    assert not quote_found("Fuel is our largest", t)  # too short to prove anything


def test_check_keeps_only_verified_items():
    c = run_check()
    assert c.pack == "airlines"
    assert [d.series for d in c.drivers] == ["fred:CPILFESL", "fred:NEWID"]
    why = {(r["kind"], r["item"].get("series") or r["item"].get("name") or r["item"].get("kpi")): r["why"]
           for r in c.rejected}
    assert why[("driver", "fred:RSGMS")] == "quote not found in the 10-K"
    assert why[("driver", "fred:HOUST")].startswith("unknown state")
    assert why[("driver", "fred:DJFUELUSGULF")] == "already a signal"
    assert why[("kpi", "Bad Name")] == "name must be snake_case"
    assert why[("edge", "no_such_kpi")].startswith("unknown KPI")
    assert [k.name for k in c.kpis] == ["fuel_share"]
    assert {(e.state, e.kpi): e.prior_mean for e in c.edges}[("input_cost", "fuel_share")] == 1.0  # clipped
    assert [o.name for o in c.operating_kpis] == ["net_yields"]


def test_failed_fetch_or_xbrl_drops_items():
    c = run_check(series_ok=lambda s: "could not fetch", kpi_ok=lambda k: "only 3 quarters")
    assert "fred:NEWID" not in [d.series for d in c.drivers]
    assert c.kpis == []
    # with fuel_share gone, its edge has no target
    assert ("input_cost", "fuel_share") not in {(e.state, e.kpi) for e in c.edges}


def test_applied_spec_loads(tmp_path):
    spec = yaml.safe_load((ROOT / "specs" / "auto" / "mar.yaml").read_text(encoding="utf-8"))
    out = apply(spec, run_check(), {"model": "test", "accession": "0000000000-26-000001"})
    assert out["kpis"]["fuel_share"]["bounds"] == [None, 100]
    assert out["ground_truth"]["xbrl"]["rules"]["fuel_share"]["kind"] == "ratio"
    assert any(s["series"] == "fred:NEWID" and "10-K:" in s["notes"] for s in out["signals"])
    path = tmp_path / "x.yaml"
    path.write_text(yaml.safe_dump(out, sort_keys=False), encoding="utf-8")
    r = load_spec(path, ROOT / "templates")
    assert "fuel_share" in r.kpis and len(r.signals) == len(spec["signals"]) + 2
    assert spec["signals"] != out["signals"]  # input not mutated


def test_output_schema_is_closed_and_inlined():
    s = output_schema(Draft)
    flat = str(s)
    assert "$ref" not in flat and "$defs" not in flat and "title" not in flat
    assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])
    driver = s["properties"]["drivers"]["items"]
    assert driver["additionalProperties"] is False and "quote" in driver["required"]


def test_long_filings_are_cut_at_item_8_not_truncated():
    text = "Item 8. Financial Statements (toc) " + "business " * 300 + "Item 8. Financial Statements " + "x " * 300
    cut, note = fit_text(text, limit=len(text) - 10)
    assert cut.endswith("business ") and "omitted" in note
    assert fit_text("short", limit=100) == ("short", "")


def test_xbrl_history_must_be_recent():
    from onboarding.llm import xbrl_history_problem

    q = {f"{y}Q{i}": [] for y in range(2014, 2019) for i in range(1, 5)}  # 20 quarters ending 2018Q4
    assert "no longer reports" in xbrl_history_problem(q, cutoff="2025Q1")
    assert xbrl_history_problem(q, cutoff="2018Q1") is None
    assert "only 3 quarters" in xbrl_history_problem({"2025Q1": [], "2025Q2": [], "2025Q3": []}, cutoff="2024Q1")
