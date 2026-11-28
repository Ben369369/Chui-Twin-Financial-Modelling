"""BLS batches and EIA series: parse saved real responses, keep API keys out of saved files. No network."""

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from adapters import batches
from adapters.bls import BlsAdapter
from adapters.eia import EiaAdapter
from adapters.http import load_snapshots
from engine.observation import RawSnapshot

RAW = Path(__file__).resolve().parent / "fixtures/raw"
KEY = "test-key-0123456789"


def snap(name: str, source: str, params: dict) -> RawSnapshot:
    p = RAW / name
    return RawSnapshot(source, datetime(2026, 11, 28, tzinfo=timezone.utc), str(p),
                       hashlib.sha256(p.read_bytes()).hexdigest(), params, "https://example.test")


class FakeResponse:
    def __init__(self, body: bytes):
        self.content, self.text = body, body.decode()

    def json(self):
        return json.loads(self.content)


class FakeClient:
    def __init__(self, bodies: list[bytes]):
        self.bodies, self.calls = list(bodies), []

    def get(self, url, params=None, headers=None):
        self.calls.append(("GET", url, dict(params or {})))
        return FakeResponse(self.bodies.pop(0))

    def post(self, url, json=None, headers=None):
        self.calls.append(("POST", url, dict(json or {})))
        return FakeResponse(self.bodies.pop(0))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CHUI_DATA_DIR", str(tmp_path))
    return tmp_path


def test_bls_batch_response_skips_unreleased_month():
    obs = BlsAdapter().normalize([snap("bls_batch_cpi_apu.json", "bls", {"series_ids": ["CUSR0000SEFV", "APU0000703112"]})])
    by = {s: sorted((o for o in obs if o.series == s), key=lambda o: o.observed_at)
          for s in ("bls:CUSR0000SEFV", "bls:APU0000703112")}
    assert [len(v) for v in by.values()] == [13, 13]  # 14 months, October 2025 not published ("-")
    assert date(2025, 10, 31) not in {o.observed_at for o in obs}
    latest = by["bls:CUSR0000SEFV"][-1]
    assert latest.observed_at == date(2026, 10, 31) and latest.value == 400.85
    assert latest.available_at == datetime(2026, 12, 10, tzinfo=timezone.utc)  # +40 days
    assert by["bls:APU0000703112"][-1].value == 6.755


def test_bls_fetch_many_is_one_query_and_key_stays_out_of_files(data_dir, monkeypatch):
    monkeypatch.setenv("CHUI_BLS_API_KEY", KEY)
    body = (RAW / "bls_batch_cpi_apu.json").read_bytes()
    client = FakeClient([body])
    a = BlsAdapter(client)
    assert a.batch_size == 50
    snaps = a.fetch_many(["bls:CUSR0000SEFV", "bls:APU0000703112"], date(2025, 9, 1), date(2026, 11, 29))
    [(method, _, sent)] = client.calls
    assert method == "POST" and sent["seriesid"] == ["CUSR0000SEFV", "APU0000703112"] and sent["registrationkey"] == KEY
    meta = next(data_dir.rglob("*.meta.json")).read_text(encoding="utf-8")
    assert KEY not in meta and KEY not in snaps[0].url
    assert len(a.normalize(load_snapshots("bls"))) == 26


def test_bls_without_key_uses_free_limits(monkeypatch):
    monkeypatch.delenv("CHUI_BLS_API_KEY", raising=False)
    assert BlsAdapter().batch_size == 25


def test_eia_daily_spot_prices():
    obs = EiaAdapter().normalize([snap("eia_jet_fuel_gulf.json", "eia", {"series_id": "PET.EER_EPJK_PF4_RGC_DPG.D"})])
    assert len(obs) == 5
    o = max(obs, key=lambda o: o.observed_at)
    assert o.series == "eia:PET.EER_EPJK_PF4_RGC_DPG.D" and o.observed_at == date(2026, 11, 24)
    assert o.value == 3.397 and o.unit == "$/GAL"
    assert o.available_at == datetime(2026, 11, 26, tzinfo=timezone.utc)  # +2 days


def test_eia_key_never_saved(data_dir, monkeypatch):
    monkeypatch.setenv("CHUI_EIA_API_KEY", KEY)
    client = FakeClient([(RAW / "eia_jet_fuel_gulf.json").read_bytes()])
    snaps = EiaAdapter(client).fetch({"series_id": "PET.EER_EPJK_PF4_RGC_DPG.D"}, date(2026, 11, 1), date(2026, 11, 29))
    [(_, _, sent)] = client.calls  # 5 rows < requested length: one page is enough
    assert sent["api_key"] == KEY
    meta = next(data_dir.rglob("*.meta.json")).read_text(encoding="utf-8")
    assert KEY not in meta and KEY not in snaps[0].url and "api_key" not in snaps[0].params


def test_eia_rejects_series_without_frequency():
    with pytest.raises(ValueError):
        EiaAdapter().params_for_series("eia:PET.RWTC")


def test_batches_group_only_multi_series_sources(monkeypatch):
    monkeypatch.delenv("CHUI_BLS_API_KEY", raising=False)
    groups = batches(["bls:A", "fred:X", "bls:B", "eia:PET.RWTC.D", "fred:Y"])
    assert [g for _, g in groups] == [["bls:A", "bls:B"], ["fred:X"], ["eia:PET.RWTC.D"], ["fred:Y"]]
