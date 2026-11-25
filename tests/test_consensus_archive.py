"""Consensus archiving: raw-first saving, point in time = fetch time, and the API key never stored."""

import json

import pytest
import requests

from adapters import consensus
from adapters.http import load_snapshots

KEY = "sk-test-0123456789"
PROVIDER = consensus.ConsensusProvider(
    name="consensus_test", key_env="CHUI_TEST_CONSENSUS_KEY", url="https://example.test/estimates",
    params={"symbol": "{ticker}", "period": "quarter"}, key_param="apikey")


class FakeResponse:
    def __init__(self, body: bytes):
        self.content, self.text = body, body.decode()


class FakeClient:
    def __init__(self, body: bytes = b'[{"symbol": "ZZZ", "date": "2026-12-31", "revenueAvg": 1.0}]', error=None):
        self.body, self.error, self.calls = body, error, []

    def get(self, url, params=None, headers=None):
        self.calls.append((url, dict(params or {})))
        if self.error:
            raise self.error
        return FakeResponse(self.body)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("CHUI_DATA_DIR", str(tmp_path))
    monkeypatch.setenv(PROVIDER.key_env, KEY)
    return tmp_path


def test_snapshot_saved_raw_without_key(env):
    client = FakeClient()
    snap = consensus.fetch_snapshot(PROVIDER, "ZZZ", client)
    url, sent = client.calls[0]
    assert sent == {"symbol": "ZZZ", "period": "quarter", "apikey": KEY}  # key is sent...
    meta = (env / snap.path).with_name((env / snap.path).name + ".meta.json").read_text(encoding="utf-8")
    assert KEY not in meta and KEY not in snap.url and "apikey" not in json.loads(meta)["params"]  # ...not stored
    assert (env / snap.path).read_bytes() == client.body  # untouched response
    [loaded] = load_snapshots("consensus_test")
    assert loaded.params["ticker"] == "ZZZ" and loaded.fetched_at == snap.fetched_at  # point in time


def test_errors_are_redacted(env):
    leak = requests.HTTPError(f"500 Server Error for url: https://example.test/estimates?apikey={KEY}")
    with pytest.raises(RuntimeError) as info:
        consensus.fetch_snapshot(PROVIDER, "ZZZ", FakeClient(error=leak))
    assert KEY not in str(info.value) and "***" in str(info.value)


def test_response_echoing_key_is_not_saved(env):
    with pytest.raises(RuntimeError):
        consensus.fetch_snapshot(PROVIDER, "ZZZ", FakeClient(body=f'{{"error": "bad key {KEY}"}}'.encode()))
    assert load_snapshots("consensus_test") == []


def test_inactive_without_key(monkeypatch):
    monkeypatch.delenv(PROVIDER.key_env, raising=False)
    assert consensus.active_providers({"t": PROVIDER}) == []
