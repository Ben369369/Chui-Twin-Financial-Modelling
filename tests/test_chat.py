"""Chat loop with a fake Claude client: no network, no API key."""

from types import SimpleNamespace as NS

import pytest

from adapters.http import data_root

pytestmark = pytest.mark.skipif(not (data_root() / "chui.sqlite").exists(), reason="no local database")


class FakeClient:
    """Replays scripted responses and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def text(t, stop="end_turn"):
    return NS(stop_reason=stop, model="claude-sonnet-5-5", content=[NS(type="text", text=t)])


def test_tool_loop_runs_tools_and_returns_actions():
    from api.chat import converse

    tool_turn = NS(stop_reason="tool_use", model="claude-sonnet-5-5", content=[
        NS(type="tool_use", id="t1", name="economy_shock", input={"series": "fred:DJFUELUSGULF", "move_pct": 30}),
        NS(type="tool_use", id="t2", name="get_scorecard", input={"ticker": "DAL"}),
    ])
    client = FakeClient([tool_turn, text("Airline margins fall.")])
    messages = [{"role": "user", "content": "What if jet fuel rises 30%?"}]
    out = converse(client, messages, system=[])
    assert out["reply"] == "Airline margins fall."
    assert [c["name"] for c in out["tool_calls"]] == ["economy_shock", "get_scorecard"]
    assert out["actions"] == [{"type": "economy_shock", "series": "fred:DJFUELUSGULF", "move": 30}]
    # Both tool results go back in ONE user message, matched by id, after the assistant turn.
    results = messages[2]["content"]
    assert messages[2]["role"] == "user" and [r["tool_use_id"] for r in results] == ["t1", "t2"]
    assert '"DAL"' in results[1]["content"] and "fallbacks" in client.requests[0]
    assert client.requests[0]["model"] == "claude-sonnet-5-5"


def test_refusal_and_tool_errors_are_handled():
    from api.chat import converse

    refused = NS(stop_reason="refusal", model="claude-sonnet-5-5", content=[])
    out = converse(FakeClient([refused]), [{"role": "user", "content": "x"}], system=[])
    assert out["stop_reason"] == "refusal" and "can't help" in out["reply"]

    bad = NS(stop_reason="tool_use", model="m", content=[NS(type="tool_use", id="t1", name="get_forecast",
                                                            input={"ticker": "NOPE", "shocks": None})])
    messages = [{"role": "user", "content": "x"}]
    out = converse(FakeClient([bad, text("No such twin.")]), messages, system=[])
    assert out["reply"] == "No such twin." and "no twin for NOPE" in messages[2]["content"][0]["content"]


def test_chat_endpoint_reports_missing_credentials(monkeypatch):
    from fastapi.testclient import TestClient

    from api.serve import app

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    c = TestClient(app)
    assert c.get("/api/chat/status").json()["configured"] is False
    assert c.post("/api/chat", json={"message": "hi"}).status_code == 503
