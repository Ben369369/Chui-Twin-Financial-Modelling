"""Sitemap counter, GDELT, factory helpers, seasonal lag and change-target KPIs."""

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml

from adapters.gdelt import GdeltAdapter
from adapters.http import PoliteClient
from adapters.scrapers.sitemap import SitemapAdapter, load_config
from engine.observation import RawSnapshot
from engine.primitives import KPIDef
from engine.spec import Spec, load_spec, resolve
from engine.primitives import load_template
from engine.twin import Twin
from onboarding.factory import clean_name, load_packs, make_news_query, pick_pack, ticker_in_infobox
from tests.synthetic import generate

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "tests/fixtures/raw"
CLIENT = PoliteClient(min_interval_s=0)


def snap(name, source, params):
    p = RAW / name
    return RawSnapshot(source, datetime(2026, 10, 1, 12, tzinfo=timezone.utc), str(p),
                       hashlib.sha256(p.read_bytes()).hexdigest(), params, "https://example.test")


def test_sitemap_counts_store_pages_only():
    a = SitemapAdapter(CLIENT, config=load_config())
    s = snap("sitemap_stores.xml", "sitemap", {"name": "chipotle_stores", "group": "live-20261001120000",
                                                "url": "x", "captured": None})
    obs = a.normalize([s])
    assert len(obs) == 1 and obs[0].value == 19  # 40 URLs, 19 are store pages
    assert obs[0].series == "sitemap:chipotle_stores" and obs[0].entity_id == "CMG"


def test_sitemap_drops_truncated_listing():
    cfg = load_config()
    cfg["chipotle_stores"] = dict(cfg["chipotle_stores"], min_valid=1000)
    s = snap("sitemap_stores.xml", "sitemap", {"name": "chipotle_stores", "group": "live-1", "url": "x", "captured": None})
    assert SitemapAdapter(CLIENT, config=cfg).normalize([s]) == []


def test_sitemap_wayback_skew_rejects_incoherent_capture():
    s = snap("sitemap_stores.xml", "sitemap", {"name": "chipotle_stores", "group": "wayback-20240101000000",
                                                "url": "x", "captured": "20240301000000"})
    assert SitemapAdapter(CLIENT, config=load_config()).normalize([s]) == []


def test_gdelt_tone():
    obs = GdeltAdapter(CLIENT).normalize([snap("gdelt_tone_chipotle.json", "gdelt", {"kind": "tone", "query": "chipotle"})])
    assert len(obs) == 30 and obs[0].series == "gdelt:tone:chipotle"
    assert obs[0].observed_at == date(2017, 1, 1) and obs[0].available_at.date() == date(2017, 1, 2)
    assert GdeltAdapter(CLIENT).params_for_series("gdelt:vol:delta air lines") == {"kind": "vol", "query": "delta air lines"}


@pytest.mark.parametrize("raw,clean", [
    ("DELTA AIR LINES, INC.", "delta air lines"),
    ("MARRIOTT INTERNATIONAL INC /MD/", "marriott"),
    ("Starbucks Corp", "starbucks"),
    ("CHIPOTLE MEXICAN GRILL INC", "chipotle mexican grill"),
])
def test_clean_name(raw, clean):
    assert clean_name(raw) == clean


def test_every_pack_resolves_to_a_valid_spec():
    packs = load_packs()
    d = packs["defaults"]
    for name, pack in packs["packs"].items():
        assert pick_pack(pack["sic"][0], packs)[0] == name
        spec = Spec.model_validate({
            "ticker": "TEST", "name": "Test", "template": pack["template"], "kpis": d["kpis"],
            "signals": pack["signals"], "edges": d["edges"],
            "exclude_from_calibration": pack.get("exclude_from_calibration", []),
        })
        resolve(spec, load_template(pack["template"], ROOT / "templates"))


def test_change_target_rejects_lags():
    with pytest.raises(ValueError):
        KPIDef(unit="pct", target="change", lag={"prior_mean": 0.5, "prior_sd": 0.1})


def _variant(**kpi_overrides):
    base = yaml.safe_load((ROOT / "tests/fixtures/specs/dummy.yaml").read_text(encoding="utf-8"))
    for k, v in kpi_overrides.items():
        base["kpis"][k] = v
    return resolve(Spec.model_validate(base), load_template("_dummy", ROOT / "templates"))


def test_change_target_end_to_end_and_waterfall_adds_up():
    rspec = _variant(zorp={"unit": "pct", "target": "change"})
    obs, gt, _, _ = generate(rspec, "2015Q1", "2024Q4")
    fitted = Twin(rspec, obs, gt).fit(datetime(2025, 2, 15, tzinfo=timezone.utc))
    m = fitted.models["zorp"]
    assert m.target == "change" and m.n_obs > 30
    assert m.coef_mean[1] > 0  # zorp rises with flux_q, so its change rises with flux_q's change
    fc = fitted.forecast(["2025Q1", "2025Q2"], n_paths=20_000)
    for p in ("2025Q1", "2025Q2"):
        total = sum(c.value for c in fc.waterfall[p]["zorp"])
        assert abs(total - fc.summary["zorp"][p]["mean"]) < 0.15, p
    assert any(c.driver == "zorp[t-1]" and c.source_refs for c in fc.waterfall["2025Q1"]["zorp"])


def test_seasonal_lag_is_learned():
    rspec = _variant(zorp={"unit": "pct", "seasonal_lag": {"prior_mean": 0.0, "prior_sd": 1.0}})
    obs, gt, _, _ = generate(rspec, "2015Q1", "2024Q4")
    # Add a strong seasonal pattern to zorp's ground truth.
    import dataclasses
    gt = [dataclasses.replace(g, value=g.value + (5.0 if g.period.endswith("Q3") else 0.0)) if g.kpi == "zorp" else g
          for g in gt]
    fitted = Twin(rspec, obs, gt).fit(datetime(2025, 2, 15, tzinfo=timezone.utc))
    m = fitted.models["zorp"]
    assert m.lags == [4] and m.lag_coef(4) > 0.3
    fc = fitted.forecast(["2025Q1", "2025Q2", "2025Q3"], n_paths=5000).summary["zorp"]
    assert fc["2025Q3"]["mean"] > fc["2025Q2"]["mean"] + 0.5  # last Q3 carried a +5 seasonal bump


def test_guidance_extraction_dal_2025q1_release():
    from adapters.edgar import extract_guidance

    rules = yaml.safe_load((ROOT / "specs/dal.yaml").read_text(encoding="utf-8"))["ground_truth"]["edgar"]["guidance"]
    s = snap("edgar_dal_2025q1_ex991.htm", "edgar",
             {"kind": "document", "accession": "0000027904-25-000020", "document": "delta_ex9901.htm",
              "acceptance": "2025-04-09T10:30:18+00:00"})
    (g,) = extract_guidance([s], "DAL", "quarter", rules)
    # "2Q25 Total Revenue YoY Down 2% - up 2%" -> midpoint 0 for 2025Q2, known at the release time
    assert (g.period, g.value, g.source) == ("2025Q2", 0.0, "guidance")
    assert g.available_at.isoformat() == "2025-04-09T10:30:18+00:00" and "span:" in g.source_ref


def test_typed_document_fallback_regex():
    from adapters.edgar import _TYPED_DOC

    row = ('<td scope="row"><a href="/Archives/edgar/data/27904/000002790426000029/deltaairlinesannouncesjune.htm">'
           'deltaairlinesannouncesjune.htm</a></td>\n  <td scope="row">EX-99.1</td>')
    assert _TYPED_DOC.findall(row) == [("deltaairlinesannouncesjune.htm", "EX-99.1")]


def test_entity_resolution_requires_ticker_in_infobox():
    assert ticker_in_infobox("traded_as = {{ubl|{{NYSE|DHI}}|[[S&P 500]] component}}", "DHI")
    assert ticker_in_infobox("traded_as = {{Nasdaq|SBUX}}", "SBUX")
    assert not ticker_in_infobox("Horton Hears a Who! by Dr. Seuss", "DHI")
    assert not ticker_in_infobox("{{NYSE|DHIX}}", "DHI")
    assert make_news_query("Target_Corporation", "TARGET CORP") == "target corporation"
    assert make_news_query("Hilton_Worldwide", "HILTON WORLDWIDE HOLDINGS INC.") == "hilton worldwide"
    assert make_news_query(None, "STARBUCKS CORP") == "starbucks"


def test_anchor_on_external_forecast():
    """A change KPI anchored on an informative external forecast should follow it,
    and the waterfall should show the anchor as a sourced driver."""
    import dataclasses
    from datetime import timedelta

    from engine.observation import ExternalForecast

    rspec = _variant(zorp={"unit": "pct", "target": "change", "anchor": "guess"})
    obs, gt, _, _ = generate(rspec, "2015Q1", "2024Q4")
    rng = np.random.default_rng(3)
    # The "guess" source knows each period's outcome to within 0.2, published 20 days before release.
    ext = [ExternalForecast("ZZZ", g.period, "zorp", "guess", g.value + 0.2 * rng.standard_normal(),
                            g.available_at - timedelta(days=20), f"test:{g.period}") for g in gt if g.kpi == "zorp"]
    fitted = Twin(rspec, obs, gt, ext).fit(datetime(2024, 12, 15, tzinfo=timezone.utc))
    m = fitted.models["zorp"]
    assert m.anchor == "guess" and m.n_anchored >= 8 and m.sigma < 1.0
    target = next(g for g in gt if g.kpi == "zorp" and g.period == "2024Q4")
    # Publish the 2024Q4 guess before as_of so it is usable.
    late = dataclasses.replace(next(e for e in ext if e.period == "2024Q4"),
                               available_at=datetime(2024, 12, 1, tzinfo=timezone.utc))
    fitted = Twin(rspec, obs, gt, [e for e in ext if e.period != "2024Q4"] + [late]).fit(
        datetime(2024, 12, 15, tzinfo=timezone.utc))
    fc = fitted.forecast(["2024Q4"], n_paths=5000)
    assert abs(fc.summary["zorp"]["2024Q4"]["mean"] - target.value) < 1.0
    assert any(c.driver == "zorp[guess]" and c.source_refs == ["test:2024Q4"] for c in fc.waterfall["2024Q4"]["zorp"])


def test_bounds_clip_paths_and_report_share():
    rspec = _variant(zorp={"unit": "pct", "bounds": [-1.0, 1.0]})
    obs, gt, _, _ = generate(rspec, "2015Q1", "2024Q4")
    fc = Twin(rspec, obs, gt).fit(datetime(2025, 2, 15, tzinfo=timezone.utc)).forecast(["2025Q1"], n_paths=4000)
    col = fc.sim.kpis["zorp"][:, 0]
    assert col.min() >= -1.0 and col.max() <= 1.0
    assert 0 < fc.summary["zorp"]["2025Q1"]["clipped_share"] <= 1
    with pytest.raises(ValueError):
        KPIDef(unit="pct", bounds=[2.0, 1.0])


def test_series_shock_scales_by_signal_weight():
    from engine.scenarios import as_shocks, series_shock

    rspec = load_spec(ROOT / "tests/fixtures/specs/dummy.yaml", ROOT / "templates")
    obs, gt, _, _ = generate(rspec, "2015Q1", "2024Q4")
    fitted = Twin(rspec, obs, gt).fit(datetime(2025, 2, 15, tzinfo=timezone.utc))
    a = series_shock(rspec, fitted.history, "syn:a", 2.0)  # sign +1, confidence 0.8
    b = series_shock(rspec, fitted.history, "syn:b", 2.0)  # sign -1, confidence 0.6, same state
    assert a.primitive == b.primitive == "flux_q"
    assert 0 < a.weight < 1 and a.weight > b.weight  # higher confidence carries more weight
    assert a.size > 0 > b.size  # sign follows the signal mapping
    assert series_shock(rspec, fitted.history, "not:used", 2.0) is None
    shocks = as_shocks(a, "2025Q1", 2.0, "syn:a +2sd")
    base = fitted.forecast(["2025Q1"], n_paths=8000, seed=4).summary["zorp"]["2025Q1"]["mean"]
    hit = fitted.forecast(["2025Q1"], n_paths=8000, seed=4, shocks=shocks).summary["zorp"]["2025Q1"]["mean"]
    assert hit > base  # flux_q -> zorp is positive
