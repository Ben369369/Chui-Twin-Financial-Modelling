"""Twin factory v1: an LLM reads the company's latest 10-K and drafts the company-specific parts of a spec.

    result = onboard(company, packs, template, sic_pack="hotels")   # factory.build_spec(..., llm=True) calls this

The model proposes; code decides. Every proposal must carry a quote copied from the 10-K, and code drops
any item whose quote is not in the filing, whose series cannot be fetched, whose XBRL concepts lack
history, or whose state or KPI is unknown. What survives is merged over the industry-pack defaults:
extra driver series, extra XBRL KPIs, and edge priors. Operating metrics outside XBRL (comps, RevPAR)
are recorded as suggestions only. The raw prompt and response are saved under data/raw/llm/ first.

Bias note: the model reads today's 10-K, and the walk-forward backtest then scores the resulting
structure on earlier quarters. Like the pack choice itself, structure chosen with hindsight; say so.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

import yaml
from pydantic import BaseModel

from adapters.edgar import FILING_DOC, REVENUE_CONCEPTS, EdgarAdapter, filings, html_to_text, quarterly_facts
from adapters.http import read_raw, save_raw, snapshot_ref
from engine.periods import period_of, shift

ROOT = Path(__file__).resolve().parents[1]
PROMPT_VERSION = "onboard_spec_v1"
PROMPT_FILE = ROOT / "prompts" / f"{PROMPT_VERSION}.md"
CATALOG = ROOT / "adapters" / "series_catalog.yaml"
MODEL = os.environ.get("CHUI_ONBOARD_MODEL", "claude-sonnet-5-5")
MAX_TEXT_CHARS = 700_000  # about 175k tokens; longer filings are cut at the financial statements, never silently
MIN_XBRL_QUARTERS = 16  # four years, so a yoy KPI has at least three years of history to calibrate on
MAX_XBRL_STALE_QUARTERS = 6  # the concept must still be reported: companies drop or rename tags
MAX_DRIVERS, MAX_KPIS = 4, 2
STRENGTH_CONFIDENCE = {"weak": 0.3, "moderate": 0.5}
NEW_EDGE_SD = 0.3
# KPI shapes for the two kinds the model may add; same structures as the pack defaults.
KPI_SHAPES = {
    "yoy": {"unit": "pct", "bounds": [-100, None], "target": "change"},
    "ratio": {"unit": "pct", "bounds": [None, 100], "lag": {"prior_mean": 0.3, "prior_sd": 0.2},
              "seasonal_lag": {"prior_mean": 0.6, "prior_sd": 0.2}},
}


# ---- what the model returns ------------------------------------------------

class PackChoice(BaseModel):
    pack: str
    reason: str
    quote: str


class Driver(BaseModel):
    series: str
    state: str
    sign: Literal[1, -1]
    lag_days: int
    transform: Literal["yoy_log", "yoy_diff"]
    strength: Literal["weak", "moderate"]
    reason: str
    quote: str


class KpiDraft(BaseModel):
    name: str
    kind: Literal["yoy", "ratio"]
    concepts: list[str]
    description: str
    reason: str
    quote: str


class EdgeDraft(BaseModel):
    state: str
    kpi: str
    prior_mean: float
    reason: str
    quote: str


class OperatingKpi(BaseModel):
    name: str
    definition: str
    quote: str


class Draft(BaseModel):
    business_summary: str
    pack: PackChoice
    drivers: list[Driver]
    kpis: list[KpiDraft]
    edges: list[EdgeDraft]
    operating_kpis: list[OperatingKpi]


def output_schema(model: type[BaseModel]) -> dict:
    """Pydantic schema in the form structured outputs accepts: refs inlined, every property required,
    no extra properties, no titles. Pydantic still validates the reply afterwards."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})

    def fix(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return fix(defs[node["$ref"].split("/")[-1]])
            out = {k: fix(v) for k, v in node.items() if k not in ("title", "default")}
            if out.get("type") == "object":
                out["required"] = list(out.get("properties", {}))
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [fix(v) for v in node]
        return node

    return fix(raw)


# ---- inputs: the 10-K, the XBRL concepts, the series catalog -----------------

@dataclass
class Filing10K:
    accession: str
    url: str
    filed: str
    text: str
    raw_ref: str
    text_note: str = ""


def latest_10k(cik: str, adapter: EdgarAdapter | None = None) -> Filing10K:
    adapter = adapter or EdgarAdapter()
    tenks = filings(adapter.fetch_submissions(cik), ["10-K"])
    if not tenks:
        raise ValueError(f"no 10-K on file for CIK {cik}")
    f = tenks[-1]
    url = FILING_DOC.format(cik=int(f.cik), acc=f.accession.replace("-", ""), name=f.primary_document)
    r = adapter.client.get(url)
    snap = save_raw("edgar", r.content, url, {"kind": "document", "form": f.form, "cik": f.cik,
                                              "accession": f.accession, "document": f.primary_document},
                    f.primary_document.rsplit(".", 1)[-1], label=f"{f.accession}_{f.primary_document}")
    text, note = fit_text(html_to_text(read_raw(snap)))
    return Filing10K(f.accession, url, f.filing_date, text, snapshot_ref(snap), note)


def fit_text(text: str, limit: int = MAX_TEXT_CHARS) -> tuple[str, str]:
    """Whole filing if it fits; else everything before Item 8 (financial statements). Raises rather than truncate."""
    if len(text) <= limit:
        return text, ""
    # The first "Item 8" is usually the table of contents; cut at the last one that leaves text before it.
    cuts = [m.start() for m in re.finditer(r"item\s*8\s*[.:-]?\s*financial\s+statements", text, re.I)]
    cut = next((c for c in reversed(cuts) if c <= limit), None)
    if cut is None or cut < limit // 4:
        raise ValueError(f"10-K text is {len(text):,} chars and has no usable Item 8 cut; raise MAX_TEXT_CHARS")
    return text[:cut], f"filing is {len(text):,} chars; sent Items 1-7 ({cut:,} chars), financial statements omitted"


def recent_cutoff(today: date | None = None) -> str:
    return shift(period_of(today or date.today(), "quarter"), -MAX_XBRL_STALE_QUARTERS)


def xbrl_history_problem(q: dict, cutoff: str) -> str | None:
    """None if quarterly facts q have enough history and are still being reported."""
    if len(q) < MIN_XBRL_QUARTERS:
        return f"only {len(q)} quarters of XBRL history (need {MIN_XBRL_QUARTERS})"
    if max(q) < cutoff:
        return f"XBRL history ends {max(q)}; the company no longer reports it"
    return None


def xbrl_concepts(facts: dict, cutoff: str | None = None) -> dict[str, str]:
    """us-gaap USD concepts with enough quarterly history that is still reported: {concept: label}."""
    cutoff = cutoff or recent_cutoff()
    out = {}
    for concept, body in facts.get("facts", {}).get("us-gaap", {}).items():
        if "USD" not in body.get("units", {}):
            continue
        if xbrl_history_problem(quarterly_facts(facts, [concept]), cutoff) is None:
            out[concept] = body.get("label") or concept
    return dict(sorted(out.items()))


def series_catalog() -> dict[str, str]:
    return yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}


# ---- the call ------------------------------------------------------------------

def render_prompt(company: str, template, packs: dict, catalog: dict[str, str], concepts: dict[str, str],
                  filing: Filing10K) -> str:
    def name(s):
        return f"{s} ({catalog[s]})" if s in catalog else s
    pack_lines = []
    for pname, p in packs["packs"].items():
        sigs = ", ".join(f"{name(s['series'])} -> {s['primitive']}" for s in p["signals"])
        pack_lines.append(f"- {pname} (SIC {', '.join(map(str, p['sic']))}): {sigs}")
    fill = {
        "company": company,
        "template": template.name,
        "primitives": "\n".join(f"- {p.name}: {p.description}" for p in template.primitives),
        "packs": "\n".join(pack_lines),
        "series_catalog": "\n".join(f"- {s}: {n}" for s, n in catalog.items()),
        "default_kpis": "\n".join(f"- {k}: {v.get('description', '')}" for k, v in packs["defaults"]["kpis"].items()),
        "xbrl_concepts": "\n".join(f"- {c}: {label}" for c, label in concepts.items()),
        "filing": f"accession {filing.accession}, filed {filing.filed}" + (f"; {filing.text_note}" if filing.text_note else ""),
        "text": filing.text,
    }
    out = PROMPT_FILE.read_text(encoding="utf-8")
    for k, v in fill.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def call_model(prompt: str, label: str, model: str = MODEL) -> tuple[Draft, dict]:
    import anthropic

    client = anthropic.Anthropic()
    req = save_raw("llm", prompt.encode("utf-8"), "anthropic:messages", {"model": model, "prompt": PROMPT_VERSION},
                   "md", label=f"{label}_prompt")
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": output_schema(Draft)}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # re-run a declined request on Anthropic's recommended fallback model
        messages=[{"role": "user", "content": prompt}],
    )
    resp = save_raw("llm", response.to_json().encode("utf-8"), "anthropic:messages",
                    {"model": response.model, "prompt": PROMPT_VERSION, "request_sha256": req.sha256},
                    "json", label=f"{label}_response")
    meta = {"model": response.model, "prompt_version": PROMPT_VERSION, "prompt_ref": snapshot_ref(req),
            "response_ref": snapshot_ref(resp), "stop_reason": response.stop_reason,
            "input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"onboarding call stopped with {response.stop_reason}; see {meta['response_ref']}")
    text = next(b.text for b in response.content if b.type == "text")
    return Draft.model_validate_json(text), meta


# ---- checks ------------------------------------------------------------------------

_NORM = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                       "\xa0": " "})


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.translate(_NORM)).strip().lower()


def quote_found(quote: str, text_norm: str, min_words: int = 6) -> bool:
    q = _norm(quote).strip(" .;:,\"'")
    return len(q.split()) >= min_words and q in text_norm


@dataclass
class Checked:
    draft: Draft
    pack: str | None
    drivers: list[Driver] = field(default_factory=list)
    kpis: list[KpiDraft] = field(default_factory=list)
    edges: list[EdgeDraft] = field(default_factory=list)
    operating_kpis: list[OperatingKpi] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


def check(draft: Draft, text: str, *, packs: dict, primitives: set[str], known_series: set[str],
          default_kpis: set[str], pack_series: Callable[[str | None], set[str]],
          series_ok: Callable[[str], str | None], kpi_ok: Callable[[KpiDraft], str | None]) -> Checked:
    """Keep only what code can verify. series_ok / kpi_ok return None if fine, else the reason to drop."""
    t = _norm(text)
    out = Checked(draft, None)

    def reject(kind: str, item: BaseModel, why: str) -> None:
        out.rejected.append({"kind": kind, "item": item.model_dump(), "why": why})

    p = draft.pack
    if p.pack != "none" and p.pack not in packs["packs"]:
        reject("pack", p, f"unknown pack {p.pack!r}")
    elif not quote_found(p.quote, t):
        reject("pack", p, "quote not found in the 10-K")
    elif p.pack != "none":
        out.pack = p.pack

    taken = set(pack_series(out.pack))
    for d in draft.drivers:
        why = (f"unknown state {d.state!r}" if d.state not in primitives
               else "already a signal" if d.series in taken
               else f"too many drivers (max {MAX_DRIVERS})" if len(out.drivers) >= MAX_DRIVERS
               else "lag_days must be 0..365" if not 0 <= d.lag_days <= 365
               else "quote not found in the 10-K" if not quote_found(d.quote, t)
               else None)
        if why is None and d.series not in known_series:
            why = (series_ok(d.series) if d.series.startswith("fred:")
                   else "series not in the catalog (only fred:<ID> may be new)")
        if why:
            reject("driver", d, why)
        else:
            out.drivers.append(d)
            taken.add(d.series)

    for k in draft.kpis:
        why = ("name must be snake_case" if not re.fullmatch(r"[a-z][a-z0-9_]{2,40}", k.name)
               else "name clashes with a default KPI" if k.name in default_kpis or k.name in {x.name for x in out.kpis}
               else f"too many KPIs (max {MAX_KPIS})" if len(out.kpis) >= MAX_KPIS
               else "no concepts" if not k.concepts
               else "quote not found in the 10-K" if not quote_found(k.quote, t)
               else kpi_ok(k))
        if why:
            reject("kpi", k, why)
        else:
            out.kpis.append(k)

    kpi_names = default_kpis | {k.name for k in out.kpis}
    seen = set()
    for e in draft.edges:
        why = (f"unknown state {e.state!r}" if e.state not in primitives
               else f"unknown KPI {e.kpi!r}" if e.kpi not in kpi_names
               else "duplicate edge" if (e.state, e.kpi) in seen
               else "quote not found in the 10-K" if not quote_found(e.quote, t)
               else None)
        if why:
            reject("edge", e, why)
        else:
            out.edges.append(e.model_copy(update={"prior_mean": max(-1.0, min(1.0, e.prior_mean))}))
            seen.add((e.state, e.kpi))

    # A new KPI with no edge into it would be forecast from its own lags only; not worth adding.
    fed = {e.kpi for e in out.edges}
    for k in [k for k in out.kpis if k.name not in fed]:
        out.kpis.remove(k)
        reject("kpi", k, "no accepted edge into it")

    for o in draft.operating_kpis:
        if quote_found(o.quote, t):
            out.operating_kpis.append(o)
        else:
            reject("operating_kpi", o, "quote not found in the 10-K")
    return out


def xbrl_kpi_check(facts: dict, cutoff: str | None = None) -> Callable[[KpiDraft], str | None]:
    reported = facts.get("facts", {}).get("us-gaap", {})
    cutoff = cutoff or recent_cutoff()

    def ok(k: KpiDraft) -> str | None:
        missing = [c for c in k.concepts if c not in reported]
        if missing:
            return f"concepts not reported by this company: {missing}"
        q = quarterly_facts(facts, k.concepts)
        if problem := xbrl_history_problem(q, cutoff):
            return problem
        if k.kind == "ratio":
            rev = quarterly_facts(facts, REVENUE_CONCEPTS)
            ratios = sorted(100 * q[p][0].value / rev[p][0].value for p in q if p in rev and rev[p][0].value)
            if len(ratios) < MIN_XBRL_QUARTERS:
                return "too few quarters with revenue to form the ratio"
            mid = ratios[len(ratios) // 2]
            if not 0 < abs(mid) <= 100:
                return f"median ratio {mid:.1f}% is outside 0..100; not a share of revenue"
        return None

    return ok


def fred_series_check(series: str) -> str | None:
    from adapters import adapter_for

    try:
        adapter = adapter_for(series)
        obs = adapter.normalize(adapter.fetch(adapter.params_for_series(series), date(2012, 1, 1),
                                              date.today() + timedelta(days=1)))
    except Exception as e:  # unknown id, network
        return f"could not fetch: {type(e).__name__}: {e}"
    if not obs:
        return "fetched but empty"
    first, last = min(o.observed_at for o in obs), max(o.observed_at for o in obs)
    if first.year > 2014 or (date.today() - last).days > 120:
        return f"history {first}..{last} too short or stale"
    return None


# ---- merge into the spec -------------------------------------------------------------

def apply(spec: dict, checked: Checked, meta: dict) -> dict:
    spec = json.loads(json.dumps(spec))  # deep copy
    tag = f"LLM {meta.get('prompt_version', PROMPT_VERSION)}"
    for d in checked.drivers:
        spec["signals"].append({"series": d.series, "primitive": d.state, "sign": d.sign, "lag_days": d.lag_days,
                                "confidence": STRENGTH_CONFIDENCE[d.strength], "half_life_days": 60,
                                "transform": d.transform, "notes": f"{tag}: {d.reason} 10-K: \"{d.quote}\""})
    rules = spec.setdefault("ground_truth", {}).setdefault("xbrl", {}).setdefault("rules", {})
    for k in checked.kpis:
        spec["kpis"][k.name] = dict(KPI_SHAPES[k.kind], description=f"{k.description} ({tag})")
        rules[k.name] = ({"kind": "yoy", "concepts": list(k.concepts)} if k.kind == "yoy" else
                         {"kind": "ratio", "numerator": list(k.concepts), "denominator": list(REVENUE_CONCEPTS),
                          "max": 100})
    edges = {(e["from"], e["to"]): e for e in spec["edges"]}
    for e in checked.edges:
        sd = edges.get((e.state, e.kpi), {}).get("prior_sd", NEW_EDGE_SD)
        edges[(e.state, e.kpi)] = {"from": e.state, "to": e.kpi, "prior_mean": round(e.prior_mean, 3), "prior_sd": sd}
    spec["edges"] = list(edges.values())
    spec["notes"] = (spec.get("notes", "") + f" {tag} ({meta.get('model')}) read 10-K {meta.get('accession')}: "
                     f"+{len(checked.drivers)} drivers, +{len(checked.kpis)} KPIs, {len(checked.edges)} edge priors, "
                     f"{len(checked.rejected)} proposals rejected; details in {spec['ticker'].lower()}.onboarding.json.")
    return spec


def report(checked: Checked, meta: dict) -> dict:
    """The sidecar written next to the spec: every accepted item with its quote, every rejection with its reason."""
    return {
        **meta,
        "business_summary": checked.draft.business_summary,
        "pack_proposed": checked.draft.pack.model_dump(),
        "accepted": {"drivers": [d.model_dump() for d in checked.drivers], "kpis": [k.model_dump() for k in checked.kpis],
                     "edges": [e.model_dump() for e in checked.edges]},
        "operating_kpis_suggested": [o.model_dump() for o in checked.operating_kpis],
        "rejected": checked.rejected,
    }


@dataclass
class OnboardResult:
    checked: Checked
    meta: dict


def onboard(company, packs: dict, template, sic_pack: str | None = None,
            adapter: EdgarAdapter | None = None) -> OnboardResult:
    """company: factory.Company. Fetches the 10-K and company facts, calls the model, checks the draft."""
    adapter = adapter or EdgarAdapter()
    filing = latest_10k(company.cik, adapter)
    facts = json.loads(read_raw(adapter.fetch_companyfacts(company.cik)))
    concepts = xbrl_concepts(facts)
    catalog = series_catalog()
    pack_series_all = {s["series"] for p in packs["packs"].values() for s in p["signals"]}
    desc = f"{company.name} (ticker {company.ticker}), SEC SIC {company.sic} ({company.sic_description})"
    if sic_pack:
        desc += f". Its SIC code maps to the '{sic_pack}' pack; choose a different pack only if that is clearly wrong."
    prompt = render_prompt(desc, template, packs, catalog, concepts, filing)
    draft, meta = call_model(prompt, label=f"onboard_{company.ticker}")
    meta.update({"accession": filing.accession, "filing_url": filing.url, "filing_ref": filing.raw_ref,
                 "text_note": filing.text_note, "xbrl_concepts_offered": len(concepts)})

    def pack_series(name):
        chosen = sic_pack or name
        return {s["series"] for s in packs["packs"][chosen]["signals"]} if chosen else set()

    checked = check(draft, filing.text, packs=packs, primitives={p.name for p in template.primitives},
                    known_series=set(catalog) | pack_series_all, default_kpis=set(packs["defaults"]["kpis"]),
                    pack_series=pack_series, series_ok=fred_series_check, kpi_ok=xbrl_kpi_check(facts))
    return OnboardResult(checked, meta)
