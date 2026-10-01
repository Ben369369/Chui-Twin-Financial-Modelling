"""Adapters parse saved real responses (tests/fixtures/raw). No network."""

import hashlib
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import yaml

from adapters.bls import BlsAdapter
from adapters.edgar import extract_ground_truth, extract_values, html_to_text
from adapters.fred import FredAdapter
from adapters.http import PoliteClient
from adapters.tsa import TsaAdapter
from adapters.wikimedia import WikimediaAdapter
from engine.observation import RawSnapshot

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "tests/fixtures/raw"
CLIENT = PoliteClient(min_interval_s=0)  # never used for requests here


def snap(name: str, source: str, params: dict, url: str = "https://example.test") -> RawSnapshot:
    p = RAW / name
    return RawSnapshot(source, datetime(2026, 9, 30, tzinfo=timezone.utc), str(p),
                       hashlib.sha256(p.read_bytes()).hexdigest(), params, url)


def test_fred_monthly_to_period_end_with_release_lag():
    obs = FredAdapter(CLIENT).normalize([snap("fred_RSFSDP.csv", "fred", {"series_id": "RSFSDP"})])
    assert len(obs) == 24  # the "." missing value is dropped
    o = obs[0]
    assert o.series == "fred:RSFSDP" and o.observed_at == date(2011, 1, 31)
    assert o.available_at == datetime(2011, 3, 17, tzinfo=timezone.utc)  # +45 days
    assert "raw:" in o.source_ref


def test_bls_months():
    obs = BlsAdapter(CLIENT).normalize([snap("bls_CES7072200003.json", "bls", {"series_id": "CES7072200003"})])
    latest = max(obs, key=lambda o: o.observed_at)
    assert latest.series == "bls:CES7072200003" and latest.observed_at == date(2026, 7, 31)
    assert latest.value == 22.08


def test_wikimedia_daily():
    obs = WikimediaAdapter(CLIENT).normalize([snap("wiki_Chipotle_Mexican_Grill.json", "wikimedia", {})])
    assert len(obs) == 40 and obs[0].series == "wiki:Chipotle_Mexican_Grill"
    assert obs[0].observed_at == date(2015, 7, 1) and obs[0].value > 0


def test_tsa_table():
    obs = TsaAdapter(CLIENT).normalize([snap("tsa_2024.html", "tsa", {"year": 2024})])
    assert len(obs) == 20
    assert obs[0].observed_at == date(2024, 1, 1) and obs[0].value == 2303507


def test_edgar_extracts_cmg_2025q3_with_spans():
    rules = yaml.safe_load((ROOT / "specs/cmg.yaml").read_text(encoding="utf-8"))["ground_truth"]["edgar"]["rules"]
    s = snap("edgar_cmg_2025q3_ex991.htm", "edgar",
             {"kind": "document", "accession": "0001058090-25-000086", "document": "ex991.htm",
              "acceptance": "2025-10-29T20:12:09+00:00"})
    rows, report = extract_ground_truth([s], "CMG", "quarter", rules)
    got = {r.kpi: r.value for r in rows}
    assert report[0]["period"] == "2025Q3"
    assert got == {"comps": 0.3, "transactions": -0.8, "check": 1.1, "rlom": 24.5}
    assert all("span:" in r.source_ref and "0001058090-25-000086" in r.source_ref for r in rows)


@pytest.mark.parametrize("text,expected", [
    ("Comparable restaurant sales decreased 4.8%", -4.8),
    ("partially offset by 2.8% fewer comparable restaurant transactions", None),
])
def test_edgar_sign_words(text, expected):
    rules = {"k": [{"pattern": r"comparable restaurant sales (?P<dir>increased|decreased) (?P<value>[\d.]+)%"}]}
    got = extract_values(text, rules)
    assert (got["k"].value if got else None) == expected


def test_html_to_text_rejoins_split_spans():
    assert html_to_text(b"<p>Mex<span>ican</span> 201<span>6</span></p><div>x</div>").split() == ["Mexican", "2016", "x"]
