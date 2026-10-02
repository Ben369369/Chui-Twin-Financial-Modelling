"""Twin factory v0: ticker -> spec, from SEC metadata and an industry pack. No LLM.

    spec = build_spec("SBUX")   # dict, ready to write as specs/auto/sbux.yaml

Steps: ticker -> CIK (SEC company_tickers.json) -> name, SIC code (submissions)
-> industry pack by SIC -> shared industry signals + company signals (Wikipedia
article found by search, GDELT news query from the cleaned name) -> XBRL ground
truth rules (revenue growth, operating margin) that work for any SEC filer.

v1 (finals) replaces the pack choice and KPI selection with an LLM reading the 10-K.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from adapters.edgar import REVENUE_CONCEPTS, EdgarAdapter, sec_user_agent
from adapters.http import PoliteClient, read_raw, save_raw

PACKS = Path(__file__).with_name("industry_packs.yaml")
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
WIKI_SEARCH = "https://en.wikipedia.org/w/api.php"
SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|plc|holdings?|group|international|the|lp|llc|sa|nv)\b\.?",
    re.I,
)


@dataclass
class Company:
    ticker: str
    cik: str
    name: str
    sic: int
    sic_description: str


def load_packs() -> dict:
    return yaml.safe_load(PACKS.read_text(encoding="utf-8"))


def lookup(ticker: str) -> Company:
    client = PoliteClient(user_agent=sec_user_agent(), min_interval_s=0.2)
    r = client.get(TICKERS_URL)
    save_raw("edgar", r.content, TICKERS_URL, {"kind": "company_tickers"}, "json", label="company_tickers")
    match = next((v for v in r.json().values() if v["ticker"].upper() == ticker.upper()), None)
    if match is None:
        raise ValueError(f"{ticker} not found in SEC company_tickers.json")
    subs = EdgarAdapter(client).fetch_submissions(str(match["cik_str"]))
    body = json.loads(read_raw(subs[0]))
    return Company(ticker.upper(), str(match["cik_str"]), body["name"], int(body.get("sic") or 0),
                   body.get("sicDescription", ""))


def clean_name(name: str) -> str:
    """'DELTA AIR LINES, INC.' -> 'delta air lines'; 'MARRIOTT INTERNATIONAL INC /MD/' -> 'marriott'."""
    n = re.sub(r"/[A-Z]{2}/", " ", name)
    n = SUFFIXES.sub(" ", n.replace(",", " ").replace(".", " "))
    return re.sub(r"\s+", " ", n).strip().lower()


def ticker_in_infobox(wikitext: str, ticker: str) -> bool:
    """True if the infobox lists the ticker, e.g. {{NYSE|DHI}} or {{Nasdaq|SBUX}}."""
    return re.search(r"\{\{\s*(?:NYSE|NASDAQ|Nasdaq|NYSE American|NYSE Arca)\s*\|\s*" + re.escape(ticker) + r"\s*\}\}",
                     wikitext, re.I) is not None


def wikipedia_article(name: str, ticker: str, max_candidates: int = 5) -> str | None:
    """Search Wikipedia and accept the first candidate whose infobox lists the ticker.
    Name matching alone is unsafe: "HORTON D R INC" found "Horton (Dr. Seuss)"."""
    client = PoliteClient(min_interval_s=1.0)
    query = f"{clean_name(name)} {ticker} company"
    r = client.get(WIKI_SEARCH, params={"action": "query", "list": "search", "srsearch": query,
                                        "srlimit": max_candidates, "format": "json"})
    save_raw("wikimedia", r.content, r.url, {"kind": "search", "query": query}, "json", label=f"search_{ticker}")
    for hit in r.json()["query"]["search"]:
        title = hit["title"]
        c = client.get(WIKI_SEARCH, params={"action": "query", "prop": "revisions", "rvprop": "content",
                                            "rvslots": "main", "rvsection": 0, "format": "json", "titles": title})
        save_raw("wikimedia", c.content, c.url, {"kind": "infobox", "title": title}, "json", label=f"infobox_{title}")
        page = next(iter(c.json()["query"]["pages"].values()))
        text = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("*", "")
        if ticker_in_infobox(text, ticker):
            return title.replace(" ", "_")
    return None


def make_news_query(article: str | None, name: str) -> str:
    """Exact-phrase GDELT query from the verified article title ("Target Corporation", not "target")."""
    if article:
        return re.sub(r"\s*\(.*?\)", "", article.replace("_", " ")).strip().lower()
    return clean_name(name)


def pick_pack(sic: int, packs: dict) -> tuple[str, dict]:
    for name, pack in packs["packs"].items():
        if sic in pack["sic"]:
            return name, pack
    raise ValueError(f"no industry pack covers SIC {sic}; add one to {PACKS.name}")


def build_spec(ticker: str, news_query: str | None = None, wiki_article: str | None = None) -> tuple[dict, dict]:
    """Returns (spec dict, provenance notes)."""
    packs = load_packs()
    company = lookup(ticker)
    pack_name, pack = pick_pack(company.sic, packs)
    d = packs["defaults"]
    article = wiki_article or wikipedia_article(company.name, company.ticker)
    query = news_query or make_news_query(article, company.name)

    signals = [dict(s) for s in pack["signals"]]
    for cs in d["company_signals"]:
        base = {k: v for k, v in cs.items() if k != "kind"}
        if cs["kind"] == "wikipedia" and article:
            signals.append({"series": f"wiki:{article}", **base})
        elif cs["kind"] == "gdelt_tone":
            signals.append({"series": f"gdelt:tone:{query}", **base})

    spec = {
        "ticker": company.ticker,
        "name": company.name.title(),
        "template": pack["template"],
        "industry": pack_name,
        "period": "quarter",
        "history_start": d["history_start"],
        "exclude_from_calibration": pack.get("exclude_from_calibration", []),
        "kpis": d["kpis"],
        "signals": signals,
        "edges": d["edges"],
        "baselines": d["baselines"],
        "ground_truth": {"xbrl": {"cik": company.cik, "rules": {
            "revenue_growth": {"kind": "yoy", "concepts": REVENUE_CONCEPTS},
            "op_margin": {"kind": "ratio", "numerator": ["OperatingIncomeLoss"], "denominator": REVENUE_CONCEPTS},
        }}},
        "notes": f"Generated by onboarding/factory.py from SEC SIC {company.sic} ({company.sic_description}).",
    }
    notes = {"cik": company.cik, "sic": company.sic, "sic_description": company.sic_description,
             "pack": pack_name, "news_query": query, "wiki_article": article,
             "wiki_verified": bool(article and not wiki_article)}
    return spec, notes


def write_spec(spec: dict, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{spec['ticker'].lower()}.yaml"
    path.write_text("# Auto-generated twin spec. Edit freely; regenerate with scripts/make_twin.py.\n"
                    + yaml.safe_dump(spec, sort_keys=False, width=120), encoding="utf-8")
    return path
