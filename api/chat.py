"""Chat assistant for the dashboard: Claude with tools over the twin API.

POST /chat          {"message": "...", "session_id": optional}  ->  reply, tool calls, dashboard actions
GET  /chat/status   whether credentials are configured, and the model in use

Every number the assistant states must come from a tool result: the tools wrap the same functions the
dashboard serves, so the chat cannot quote a figure the system did not produce. The model comes from
config (CHUI_CHAT_MODEL, default claude-sonnet-5-5). The system prompt is versioned in prompts/.
Conversation history is kept server-side and only ever appended to.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
PROMPT_FILE = ROOT / "prompts" / "chat_v1.md"
MODEL = os.environ.get("CHUI_CHAT_MODEL", "claude-sonnet-5-5")
MAX_TOOL_ROUNDS = 8
DOCS = {
    "readme": "README.md",
    "model": "docs/model.md",
    "provenance": "provenance.md",
    "coverage": "docs/coverage_and_roadmap.md",
    "sealed_forecasts": "docs/sealed_forecasts.md",
}

router = APIRouter()
_sessions: dict[str, list] = {}
_lock = threading.Lock()


def _schema(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or list(properties),
            "additionalProperties": False}


TOOLS = [
    {"name": "list_twins", "strict": True,
     "description": "List every company twin: ticker, name, KPIs, the data series it uses, and whether it "
                    "was hand-built or built by the twin factory from a ticker.",
     "input_schema": _schema({})},
    {"name": "get_forecast", "strict": True,
     "description": "Forecast one company's KPIs for its next quarters: median and 80% range, the gap to "
                    "guidance or consensus, and what drives the next quarter (each driver names its data "
                    "series). Optionally apply scenario shocks to hidden states (demand, capacity, price, "
                    "input_cost, labor, sentiment, expansion) in standard deviations; results then include "
                    "the change versus the baseline.",
     "input_schema": _schema({
         "ticker": {"type": "string", "description": "e.g. CMG, DAL"},
         "shocks": {"type": ["array", "null"], "items": _schema({
             "state": {"type": "string", "description": "hidden state name, e.g. sentiment"},
             "size_sd": {"type": "number", "description": "shock size in sd; negative is bad news for demand-like states"},
             "start_period": {"type": ["string", "null"], "description": "e.g. 2026Q4; null = the current quarter"},
             "half_life_quarters": {"type": ["number", "null"], "description": "how fast it fades; null = 1"},
         })},
     })},
    {"name": "economy_shock", "strict": True,
     "description": "Move one shared data series (e.g. jet fuel, restaurant sales, TSA travelers) by a "
                    "percent year over year and see every twin that uses it respond next quarter. Use "
                    "list_shared_series for valid series ids.",
     "input_schema": _schema({
         "series": {"type": "string", "description": "series id, e.g. fred:DJFUELUSGULF"},
         "move_pct": {"type": "number", "description": "percent year over year, e.g. 30 or -5"},
     })},
    {"name": "list_shared_series", "strict": True,
     "description": "Data series used by the twins with readable names, most widely shared first.",
     "input_schema": _schema({})},
    {"name": "get_scorecard", "strict": True,
     "description": "Walk-forward backtest results: for each twin and KPI, mean error and CRPS skill versus "
                    "'same as last quarter' and 'same quarter last year'. Positive skill means the twin wins.",
     "input_schema": _schema({"ticker": {"type": ["string", "null"], "description": "one ticker, or null for all"}})},
    {"name": "shock_library", "strict": True,
     "description": "Measured real shocks (2015 food-safety crisis, 2024 airline IT outage, COVID): how deep "
                    "they went and how fast they faded, from reported revenue or comps.",
     "input_schema": _schema({})},
    {"name": "read_doc", "strict": True,
     "description": "Read a project document to explain how the system works: readme (overview), model "
                    "(the math), provenance (data sources and legal terms), coverage (industries and "
                    "roadmap), sealed_forecasts (live out-of-sample tests).",
     "input_schema": _schema({"name": {"type": "string", "enum": list(DOCS)}})},
]


# ---- tool implementations -------------------------------------------------------

def _drivers(rows: list[dict], top: int = 6) -> list[dict]:
    agg: dict[tuple, dict] = {}
    for c in rows:
        key = (c["driver"], c["signal"])
        cur = agg.setdefault(key, {"driver": c["driver"], "signal": c["signal"], "points": 0.0, "source": None})
        cur["points"] += c["value"]
        if c["source_refs"] and not cur["source"]:
            cur["source"] = c["source_refs"][0][:140]
    out = sorted(agg.values(), key=lambda d: -abs(d["points"]))[:top]
    for d in out:
        d["points"] = round(d["points"], 2)
    return out


def _summary(forecast: dict) -> dict:
    return {k: {p: {q: round(v[q], 2) for q in ("p10", "p50", "p90")} for p, v in by_p.items()}
            for k, by_p in forecast.items()}


def tool_get_forecast(ticker: str, shocks: list[dict] | None) -> tuple[dict, list[dict]]:
    from api import main

    ticker = ticker.upper()
    if ticker not in main.spec_paths():
        return {"error": f"no twin for {ticker}", "known": sorted(main.spec_paths())}, []
    fitted = main._fitted(ticker)
    # A shock "now" starts in the current calendar quarter, not in a finished-but-unreported one.
    first = max(fitted.next_unreported_period(), fitted.history.latest_period)
    shock_args, ui_shocks = [], []
    for s in shocks or []:
        period = s.get("start_period") or first
        hl = s.get("half_life_quarters") or 1.0
        shock_args.append(f"{s['state']}:{period}:{s['size_sd']}:{hl}")
        ui_shocks.append({"primitive": s["state"], "period": period, "size": s["size_sd"], "halfLife": hl})
    try:
        rec = main.forecast(ticker, shock=shock_args, paths=4000, as_of=None)
    except (HTTPException, ValueError) as e:
        return {"error": str(getattr(e, "detail", e))}, []
    period = sorted(next(iter(rec["forecast"].values())))[0]
    result = {
        "ticker": ticker, "as_of": rec["as_of"], "next_quarter": period,
        "forecast": _summary(rec["forecast"]),
        "expectation_gaps": [{"kpi": g["kpi"], "period": g["period"], "source": g["source"],
                              "expectation": round(g["expectation"], 2), "twin_minus_expectation": round(g["gap_mean"], 2),
                              "prob_above": round(g["prob_above"], 2)} for g in rec["expectation_gaps"]],
        "drivers_next_quarter": {k: _drivers(rows) for k, rows in rec["waterfall"][period].items()},
    }
    if "scenario" in rec:
        result["scenario"] = {"shocks": shock_args, "forecast": _summary(rec["scenario"]["forecast"]),
                              "change_in_mean": {k: {p: round(v, 2) for p, v in by.items()}
                                                 for k, by in rec["scenario"]["delta_mean"].items()}}
    return result, [{"type": "open_twin", "ticker": ticker, "shocks": ui_shocks}]


def tool_economy_shock(series: str, move_pct: float) -> tuple[dict, list[dict]]:
    from api import main

    try:
        res = main.portfolio_shock(series=series, size=None, move=move_pct, half_life=2.0, paths=2000)
    except HTTPException as e:
        return {"error": e.detail}, []
    out = {"series": series, "label": res["label"], "move_pct": move_pct, "twins": [
        {"ticker": t["ticker"], "state": t["primitive"], "state_shock_sd": round(t["state_shock_sd"], 2),
         "period": t["period"], "change_next_quarter": {k: round(v[t["period"]], 2) for k, v in t["impact"].items()}}
        for t in res["twins"]]}
    return out, [{"type": "economy_shock", "series": series, "move": move_pct}]


def tool_get_scorecard(ticker: str | None) -> dict:
    from api import main

    sc = main.scorecard()
    rows = [{"ticker": t["ticker"], "industry": t["industry"], "built_by": t["built_by"], "kpi": k,
             "quarters": v["n"], "mean_error": round(v["mae_twin"], 2),
             "mean_error_last_quarter": v["mae_naive"] and round(v["mae_naive"], 2),
             "skill_vs_last_quarter": v["skill_naive"] and round(v["skill_naive"], 2),
             "skill_vs_last_year": v["skill_seasonal"] and round(v["skill_seasonal"], 2)}
            for t in sc["twins"] for k, v in t["score"]["kpis"].items() if not ticker or t["ticker"] == ticker.upper()]
    wins = sum(1 for r in rows if (r["skill_vs_last_quarter"] or -1) > 0)
    return {"generated": sc["generated"], "rows": rows, "beats_last_quarter": f"{wins} of {len(rows)}"}


def run_tool(name: str, args: dict) -> tuple[str, list[dict], str]:
    """Returns (JSON result for the model, dashboard actions, one-line summary for the UI)."""
    from api import main

    actions: list[dict] = []
    if name == "list_twins":
        result = main.list_twins()
        summary = f"Listed {len(result)} twins"
    elif name == "get_forecast":
        result, actions = tool_get_forecast(args["ticker"], args.get("shocks"))
        shocks = ", ".join(f"{s['state']} {s['size_sd']:+g} sd" for s in args.get("shocks") or [])
        summary = f"Forecast {args['ticker'].upper()}" + (f" with {shocks}" if shocks else "")
    elif name == "economy_shock":
        result, actions = tool_economy_shock(args["series"], args["move_pct"])
        summary = f"Economy shock: {result.get('label', args['series'])} {args['move_pct']:+g}%"
    elif name == "list_shared_series":
        result = [{"series": s["series"], "label": s["label"], "twins": [t["ticker"] for t in s["twins"]]}
                  for s in main.shared_series()]
        summary = "Listed shared data series"
    elif name == "get_scorecard":
        result = tool_get_scorecard(args.get("ticker"))
        summary = "Read the scorecard" + (f" for {args['ticker'].upper()}" if args.get("ticker") else "")
    elif name == "shock_library":
        lib = main.shock_library()["shocks"]
        result = [{k: s[k] for k in ("name", "ticker", "event", "note", "trough_deviation_pct",
                                     "half_life_quarters", "half_recovered_by")} for s in lib]
        summary = "Read the measured shock library"
    elif name == "read_doc":
        result = {"name": args["name"], "text": (ROOT / DOCS[args["name"]]).read_text(encoding="utf-8")[:14000]}
        summary = f"Read {DOCS[args['name']]}"
    else:
        result, summary = {"error": f"unknown tool {name}"}, f"Unknown tool {name}"
    return json.dumps(result, default=str), actions, summary


# ---- the loop ----------------------------------------------------------------------

class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


def configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def converse(client, messages: list, system: list) -> dict:
    """Run the tool loop on `messages` (appended in place). Returns reply, tool calls and actions."""
    calls, actions = [], []
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=system,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # re-run a declined request on Anthropic's recommended fallback model
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "refusal":
            return {"reply": "I can't help with that request. Try asking about a twin, a scenario or how the "
                             "system works.", "tool_calls": calls, "actions": actions, "stop_reason": "refusal"}
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if response.stop_reason != "tool_use" or not tool_uses:
            text = "\n\n".join(b.text for b in response.content if b.type == "text").strip()
            return {"reply": text or "(no answer)", "tool_calls": calls, "actions": actions,
                    "stop_reason": response.stop_reason, "model": response.model}
        results = []
        for tu in tool_uses:
            try:
                content, acts, summary = run_tool(tu.name, dict(tu.input))
                results.append({"type": "tool_result", "tool_use_id": tu.id, "content": content})
            except Exception as e:  # a failing tool is reported to the model, never dropped
                summary, acts = f"{tu.name} failed: {type(e).__name__}", []
                results.append({"type": "tool_result", "tool_use_id": tu.id, "is_error": True,
                                "content": f"{type(e).__name__}: {e}"})
            calls.append({"name": tu.name, "input": dict(tu.input), "summary": summary})
            actions.extend(acts)
        messages.append({"role": "user", "content": results})  # all results in one message
    return {"reply": "I ran out of steps on that one. Try a narrower question.", "tool_calls": calls,
            "actions": actions, "stop_reason": "max_tool_rounds"}


@router.get("/chat/status")
def chat_status() -> dict:
    return {"configured": configured(), "model": MODEL, "prompt": PROMPT_FILE.name}


@router.post("/chat")
def chat(body: ChatIn) -> dict:
    if not configured():
        raise HTTPException(503, "Chat is not configured: set ANTHROPIC_API_KEY and restart the server.")
    system = [{"type": "text", "text": PROMPT_FILE.read_text(encoding="utf-8"), "cache_control": {"type": "ephemeral"}}]
    sid = body.session_id or uuid.uuid4().hex
    with _lock:
        messages = _sessions.setdefault(sid, [])
    messages.append({"role": "user", "content": body.message})
    try:
        out = converse(anthropic.Anthropic(), messages, system)
    except anthropic.AuthenticationError:
        raise HTTPException(503, "The Anthropic API key was rejected.")
    except anthropic.RateLimitError:
        raise HTTPException(429, "Rate limited by the Anthropic API; try again in a minute.")
    except anthropic.APIStatusError as e:
        raise HTTPException(502, f"Anthropic API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        raise HTTPException(502, "Could not reach the Anthropic API.")
    return {"session_id": sid, **out}
