"""SEC EDGAR: submissions index, filing documents, XBRL company facts.

User-Agent comes from env var CHUI_SEC_USER_AGENT ("Name email"), as SEC's fair
access policy requires. Rate limit: well under 10 requests per second.

Ground truth from earnings releases is extracted by `extract_ground_truth`,
driven by regex rules that live in the company spec, so this module stays
company-agnostic. Every extracted value keeps the text span it came from.
available_at is the filing's EDGAR acceptance time (UTC).
"""

from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from adapters.base import Adapter
from adapters.http import PoliteClient, read_raw, save_raw, snapshot_ref
from engine.observation import ExternalForecast, GroundTruth, Observation, RawSnapshot
from engine.periods import bounds, period_of, shift

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik10}.json"
SUBMISSIONS_PAGE = "https://data.sec.gov/submissions/{name}"
FILING_INDEX = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/index.json"
FILING_DOC = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{name}"
FILING_INDEX_HTML = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{accession}-index.htm"
DOCUMENT_TYPE_PREFIX = "EX-99"
_TYPED_DOC = re.compile(r'<a href="[^"]*/([^"/]+)">[^<]*</a>\s*</td>\s*<td[^>]*>\s*([A-Z0-9.\-]+)\s*</td>')
COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"

NEGATIVE_WORDS = re.compile(r"decreas|declin|lower|down|negative|fell|fewer|drop|reduc", re.I)
MONTH_DATE = "%B %d %Y"
DOCUMENT_PATTERN = r"ex-?99.*\.(htm|html|txt)$"
PERIOD_PATTERN = r"quarter(?:\s+and\s+(?:full\s+)?(?:fiscal\s+)?year)?\s+ended\s+([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})"


def sec_user_agent() -> str:
    ua = os.environ.get("CHUI_SEC_USER_AGENT", "").strip()
    if "@" not in ua:
        raise RuntimeError('Set CHUI_SEC_USER_AGENT to "Your Name you@example.com" (SEC requires a contact).')
    return ua


def _cik10(cik: str | int) -> str:
    return f"{int(cik):010d}"


@dataclass(frozen=True)
class Filing:
    cik: str
    accession: str
    form: str
    filing_date: str
    acceptance: datetime
    report_date: str
    items: str
    primary_document: str


class EdgarAdapter(Adapter):
    source = "edgar"
    prefix = "edgar"

    def __init__(self, client: PoliteClient | None = None):
        self.client = client or PoliteClient(user_agent=sec_user_agent(), min_interval_s=0.2)

    # ---- fetching -------------------------------------------------------

    def fetch_submissions(self, cik: str) -> list[RawSnapshot]:
        url = SUBMISSIONS.format(cik10=_cik10(cik))
        r = self.client.get(url)
        snaps = [save_raw(self.source, r.content, url, {"kind": "submissions", "cik": str(int(cik))}, "json",
                          label=f"submissions_{int(cik)}")]
        for page in r.json()["filings"].get("files", []):
            purl = SUBMISSIONS_PAGE.format(name=page["name"])
            pr = self.client.get(purl)
            snaps.append(save_raw(self.source, pr.content, purl, {"kind": "submissions_page", "cik": str(int(cik))},
                                  "json", label=page["name"]))
        return snaps

    def fetch_documents(self, filing: Filing, name_pattern: str) -> list[RawSnapshot]:
        acc = filing.accession.replace("-", "")
        idx_url = FILING_INDEX.format(cik=int(filing.cik), acc=acc)
        idx = self.client.get(idx_url)
        base = {"cik": filing.cik, "accession": filing.accession, "form": filing.form,
                "acceptance": filing.acceptance.isoformat(), "filing_date": filing.filing_date}
        snaps = [save_raw(self.source, idx.content, idx_url, dict(base, kind="index"), "json",
                          label=f"{filing.accession}_index")]
        names = [i["name"] for i in idx.json()["directory"]["item"]]
        wanted = [n for n in names if re.search(name_pattern, n, re.I)]
        if not wanted:
            # File names are not reliable (e.g. "deltaairlinesannouncesjune.htm"); fall back to the
            # document type column of the filing's HTML index.
            html_url = FILING_INDEX_HTML.format(cik=int(filing.cik), acc=acc, accession=filing.accession)
            h = self.client.get(html_url)
            snaps.append(save_raw(self.source, h.content, html_url, dict(base, kind="index_html"), "htm",
                                  label=f"{filing.accession}_index_html"))
            wanted = [n for n, t in _TYPED_DOC.findall(h.text) if t.upper().startswith(DOCUMENT_TYPE_PREFIX)]
        for name in wanted:
            url = FILING_DOC.format(cik=int(filing.cik), acc=acc, name=name)
            d = self.client.get(url)
            snaps.append(save_raw(self.source, d.content, url, dict(base, kind="document", document=name),
                                  name.rsplit(".", 1)[-1], label=f"{filing.accession}_{name}"))
        return snaps

    def fetch_companyfacts(self, cik: str) -> RawSnapshot:
        url = COMPANYFACTS.format(cik10=_cik10(cik))
        r = self.client.get(url)
        return save_raw(self.source, r.content, url, {"kind": "companyfacts", "cik": str(int(cik))}, "json",
                        label=f"companyfacts_{int(cik)}")

    def fetch(self, params: dict, start: date, end: date) -> list[RawSnapshot]:
        """params: cik, forms (list), items (list, optional), document_pattern (regex)."""
        subs = self.fetch_submissions(params["cik"])
        snaps = list(subs)
        for f in filings(subs, params.get("forms", ["8-K"]), params.get("items")):
            if start <= date.fromisoformat(f.filing_date) <= end:
                snaps += self.fetch_documents(f, params.get("document_pattern", DOCUMENT_PATTERN))
        return snaps

    def normalize(self, snapshots: list[RawSnapshot]) -> list[Observation]:
        """XBRL company facts -> observations "xbrl:<concept>" (duration facts, USD)."""
        out = []
        for snap in snapshots:
            if snap.params.get("kind") != "companyfacts":
                continue
            facts = json.loads(read_raw(snap))
            ref = snapshot_ref(snap)
            for concept, body in facts.get("facts", {}).get("us-gaap", {}).items():
                for unit, rows in body.get("units", {}).items():
                    for row in rows:
                        if "start" not in row or row.get("form") not in ("10-Q", "10-K"):
                            continue
                        start, end = date.fromisoformat(row["start"]), date.fromisoformat(row["end"])
                        if not 80 <= (end - start).days <= 100:
                            continue  # keep single-quarter facts only
                        out.append(Observation(
                            entity_id=str(int(facts["cik"])), source=self.source, series=f"xbrl:{concept}",
                            observed_at=end,
                            available_at=datetime.combine(date.fromisoformat(row["filed"]) + timedelta(days=1), time(0), timezone.utc),
                            value=float(row["val"]), unit=unit, geo=None, source_ref=f"{ref} | accn:{row['accn']}",
                        ))
        return out


def filings(submission_snaps: list[RawSnapshot], forms: list[str], items: list[str] | None = None) -> list[Filing]:
    out: dict[str, Filing] = {}
    for snap in submission_snaps:
        body = json.loads(read_raw(snap))
        cols = body["filings"]["recent"] if snap.params.get("kind") == "submissions" else body
        for i in range(len(cols["accessionNumber"])):
            if cols["form"][i] not in forms:
                continue
            if items and not any(it in cols["items"][i].split(",") for it in items):
                continue
            acc = cols["accessionNumber"][i]
            out[acc] = Filing(
                cik=snap.params["cik"], accession=acc, form=cols["form"][i], filing_date=cols["filingDate"][i],
                acceptance=datetime.fromisoformat(cols["acceptanceDateTime"][i].replace("Z", "+00:00")),
                report_date=cols["reportDate"][i], items=cols["items"][i], primary_document=cols["primaryDocument"][i],
            )
    return sorted(out.values(), key=lambda f: f.acceptance)


_BLOCK_TAGS = r"p|div|br|tr|td|th|li|table|h[1-6]|hr"
_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4}
ORDINAL_PERIOD_PATTERN = (
    r"\b(first|second|third|fourth)\s+quarter\s+(?:and\s+(?:full\s+)?(?:fiscal\s+)?year\s+)?"
    r"(?:of\s+)?(?:fiscal\s+)?(\d{4})\b"
)
_CHAR_MAP = str.maketrans({"\xa0": " ", "\ufeff": "", "\u2019": "'", "\u2014": "-", "\u2013": "-", "\u2022": " "})


def html_to_text(raw: bytes) -> str:
    """Block tags become spaces; inline tags (span, font, b) vanish, so words split across spans rejoin."""
    t = raw.decode("utf-8", errors="replace")
    t = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>", " ", t)
    t = re.sub(rf"(?i)</?(?:{_BLOCK_TAGS})\b[^>]*>", " ", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t).translate(_CHAR_MAP)
    return re.sub(r"\s+", " ", t)


def detect_period(text: str, freq: str, pattern: str = PERIOD_PATTERN) -> str | None:
    """Period from "quarter ended <Month d, yyyy>", else from "<ordinal> quarter <yyyy>" (fiscal = calendar)."""
    head = text[:4000]
    m = re.search(pattern, head)
    if m:
        clean = re.sub(r"[.,]", "", m.group(1))
        try:
            return period_of(datetime.strptime(clean, MONTH_DATE).date(), freq)
        except ValueError:
            pass
    m = re.search(ORDINAL_PERIOD_PATTERN, head, re.I)
    if m and freq == "quarter":
        return f"{m.group(2)}Q{_ORDINALS[m.group(1).lower()]}"
    return None


@dataclass
class Extraction:
    kpi: str
    value: float
    span: str
    rule: int


def extract_values(text: str, rules: dict[str, list[dict]]) -> dict[str, Extraction]:
    """rules: {kpi: [{pattern: regex with (?P<value>..) and optional (?P<dir>..), scale: 1.0}, ...]}.
    The first matching rule wins. A `dir` group containing a negative word flips the sign."""
    out = {}
    for kpi, candidates in rules.items():
        for i, rule in enumerate(candidates):
            m = re.search(rule["pattern"], text, re.I)
            if not m:
                continue
            v = float(m.group("value").replace(",", "")) * float(rule.get("scale", 1.0))
            gd = m.groupdict()
            if gd.get("dir") and NEGATIVE_WORDS.search(gd["dir"]):
                v = -abs(v)
            if rule.get("negate"):
                v = -v
            out[kpi] = Extraction(kpi, v, m.group(0), i)
            break
    return out


def extract_ground_truth(snapshots: list[RawSnapshot], entity_id: str, freq: str, rules: dict[str, list[dict]],
                         period_pattern: str = PERIOD_PATTERN) -> tuple[list[GroundTruth], list[dict]]:
    """Returns ground-truth rows and a per-document report (for coverage checks)."""
    rows, report = [], []
    for snap in snapshots:
        if snap.params.get("kind") != "document":
            continue
        text = html_to_text(read_raw(snap))
        period = detect_period(text, freq, period_pattern)
        found = extract_values(text, rules) if period else {}
        report.append({"accession": snap.params["accession"], "period": period, "found": sorted(found),
                       "missing": sorted(set(rules) - set(found))})
        for kpi, ex in found.items():
            rows.append(GroundTruth(
                entity_id=entity_id, period=period, kpi=kpi, value=ex.value,
                available_at=datetime.fromisoformat(snap.params["acceptance"]),
                source_ref=f"SEC {snap.params['accession']} {snap.params['document']} | {snapshot_ref(snap)} | span: {ex.span!r}",
                confidence=0.95, verified=False,
            ))
    return rows, report


# ---- XBRL company facts -> ground truth ---------------------------------------

# Common us-gaap revenue concepts, most specific first. Specs may override.
REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
]

@dataclass(frozen=True)
class Fact:
    period: str
    value: float
    filed: date
    accn: str
    concept: str
    derived: bool = False  # True for Q4 = FY - 9M YTD
    end: date | None = None  # the fiscal period's last day (fiscal quarters need not end with a calendar quarter)


def _days(row: dict) -> int:
    return (date.fromisoformat(row["end"]) - date.fromisoformat(row["start"])).days


def quarterly_facts(facts: dict, concepts: list[str], freq: str = "quarter", unit: str = "USD") -> dict[str, list[Fact]]:
    """Single-quarter values per period from every filing that reported them, across all
    listed concepts (a company may switch concepts, e.g. revenue under ASC 606). Sorted by
    filing date, so the first entry is what was known first: point-in-time safe.
    Q4 is derived as FY minus the 9-month YTD when a filing has no single-quarter Q4."""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    out: dict[str, list[Fact]] = {}
    for concept in concepts:
        rows = [r for r in gaap.get(concept, {}).get("units", {}).get(unit, []) if "start" in r]
        direct = set()
        for r in rows:
            if 80 <= _days(r) <= 100:
                p = period_of(date.fromisoformat(r["end"]), freq)
                direct.add((p, r["accn"]))
                out.setdefault(p, []).append(Fact(p, float(r["val"]), date.fromisoformat(r["filed"]), r["accn"], concept,
                                                  end=date.fromisoformat(r["end"])))
        ytd9 = [r for r in rows if 260 <= _days(r) <= 285]
        for fy in (r for r in rows if 350 <= _days(r) <= 380):
            end = date.fromisoformat(fy["end"])
            p = period_of(end, freq)
            if (p, fy["accn"]) in direct:
                continue
            # Use the 9M value as known when the annual report was filed.
            nine = sorted((r for r in ytd9 if r["start"] == fy["start"] and r["filed"] <= fy["filed"]
                           and 80 <= (end - date.fromisoformat(r["end"])).days <= 100), key=lambda r: r["filed"])
            if nine:
                out.setdefault(p, []).append(Fact(p, float(fy["val"]) - float(nine[-1]["val"]),
                                                  date.fromisoformat(fy["filed"]), fy["accn"], concept, True, end))
    # Earliest filing first (point in time); within one filing, the highest-priority concept wins.
    # Concepts differ in scope: McDonald's tags company-operated sales as SalesRevenueGoodsNet next to
    # total Revenues, and taking the narrower one put its "margin" near 100%.
    rank = {c: i for i, c in enumerate(concepts)}
    return {p: sorted(fs, key=lambda f: (f.filed, rank[f.concept], f.derived)) for p, fs in out.items()}


def _known_by(facts: list[Fact], when: date) -> Fact | None:
    """The most recent filing's value as of `when`; within that filing, the highest-priority concept."""
    known = [f for f in facts if f.filed <= when]
    if not known:
        return None
    latest = max(f.filed for f in known)
    return next(f for f in known if f.filed == latest)


EARNINGS_ITEM = "2.02"  # 8-K item "Results of Operations and Financial Condition": the earnings release


def earnings_releases(submission_snaps: list[RawSnapshot]) -> list[Filing]:
    """Every 8-K filed under item 2.02, oldest first."""
    return filings(submission_snaps, ["8-K"], [EARNINGS_ITEM])


def first_release(releases: list[Filing], period_end: date, filed: date) -> Filing | None:
    """The first earnings release after the period ended and no later than the 10-Q/10-K that reported it.
    The release carries the income statement, so its figures were public from that moment."""
    # Compare EDGAR filing dates (US Eastern calendar days, like `filed`): an evening release has a UTC
    # acceptance time on the next day.
    return next((f for f in releases if period_end < date.fromisoformat(f.filing_date) <= filed), None)


def xbrl_ground_truth(snap: RawSnapshot, entity_id: str, freq: str, rules: dict[str, dict],
                      releases: list[Filing] | None = None) -> list[GroundTruth]:
    """rules: {kpi: {kind: yoy, concepts: [...]}} or {kind: ratio, numerator: [...], denominator: [...]}
    or {kind: value, concepts: [...], scale: 1.0}. Percent outputs are x100.
    One row per KPI per period, from the period's first filing. available_at is the earnings release
    (8-K item 2.02) that preceded that filing when there is one, else the filing date + 1 day. Dating at
    the 10-Q alone put backtest forecasts after the results were public (Q4: about a month after)."""
    facts = json.loads(read_raw(snap))
    ref = snapshot_ref(snap)
    rows: list[GroundTruth] = []
    for kpi, rule in rules.items():
        kind = rule["kind"]
        main = quarterly_facts(facts, rule["concepts"] if kind != "ratio" else rule["numerator"], freq)
        other = quarterly_facts(facts, rule["denominator"], freq) if kind == "ratio" else {}
        for p, fs in sorted(main.items()):
            first = fs[0]
            when = first.filed
            if kind == "yoy":
                # Compare like with like: concepts can differ in scope across a switch.
                prior = main.get(shift(p, -4), [])
                base = _known_by([f for f in prior if f.concept == first.concept], when) or _known_by(prior, when)
                if base is None or base.value == 0:
                    continue
                value, detail = 100.0 * (first.value / base.value - 1.0), f"{first.concept} vs {base.accn}"
            elif kind == "ratio":
                den = _known_by(other.get(p, []), when)
                if den is None or den.value == 0:
                    continue
                value, detail = 100.0 * first.value / den.value, f"{first.concept}/{den.concept}"
                if rule.get("max") is not None and value > rule["max"]:
                    print(f"  xbrl {kpi} {p}: {value:.1f} exceeds max {rule['max']} ({detail}); dropped as a scope mismatch")
                    continue
            else:
                value, detail = first.value * float(rule.get("scale", 1.0)), first.concept
            rel = first_release(releases or [], first.end or bounds(p)[1], when)
            fallback = datetime.combine(when + timedelta(days=1), time(0), timezone.utc)
            available = min(rel.acceptance, fallback) if rel else fallback
            released = f" released 8-K accn:{rel.accession}" if rel else ""
            rows.append(GroundTruth(
                entity_id=entity_id, period=p, kpi=kpi, value=value,
                available_at=available,
                source_ref=f"SEC XBRL accn:{first.accn} {detail}{' (Q4 = FY - 9M)' if first.derived else ''}"
                           f"{released} | {ref}",
                confidence=0.99, verified=False,
            ))
    return rows


# ---- guidance in earnings releases -> external forecasts ------------------------

_FLAT = re.compile(r"^\s*(flat|unchanged)\s*$", re.I)
# Conventional readings of worded guidance ("low-single digits", "mid-teens"), in percent.
QUALITATIVE_RANGES = {
    ("low", "single"): (1, 3), ("mid", "single"): (4, 6), ("high", "single"): (7, 9),
    ("low", "teens"): (11, 13), ("mid", "teens"): (14, 16), ("high", "teens"): (17, 19),
    ("low", "double"): (10, 13), ("mid", "double"): (14, 16), ("high", "double"): (17, 19),
}
_ORDINAL_Q = {"first": 1, "second": 2, "third": 3, "fourth": 4}


def worded_range(qual: str, band: str, qual2: str | None = None) -> tuple[float, float]:
    """'low' + 'single' -> (1, 3); 'low' to 'mid' + 'single' -> (1, 6)."""
    b = "teens" if "teen" in band.lower() else "double" if "double" in band.lower() else "single"
    lo = QUALITATIVE_RANGES[(qual.lower(), b)][0]
    hi = QUALITATIVE_RANGES[((qual2 or qual).lower(), b)][1]
    return lo, hi


def _signed(number: str | None, direction: str | None) -> float:
    if number is None or _FLAT.match(number):
        return 0.0
    v = float(number)
    return -v if direction and NEGATIVE_WORDS.search(direction) or direction in ("-", "−") else v


def extract_guidance(snapshots: list[RawSnapshot], entity_id: str, freq: str,
                     rules: dict[str, list[dict]]) -> list[ExternalForecast]:
    """rules: {kpi: [{pattern, period: explicit | release_quarter}]}.
    Patterns use groups lo, hi (numbers or "flat"), optional lo_dir / hi_dir (sign words),
    or qual (low|mid|high) + band (single digit|teens) for worded ranges,
    and for period: explicit, q (1-4) and yy (two-digit year). The value is the range midpoint.
    release_quarter = the quarter in progress when the release was filed."""
    out: list[ExternalForecast] = []
    for snap in snapshots:
        if snap.params.get("kind") != "document":
            continue
        text = html_to_text(read_raw(snap))
        accepted = datetime.fromisoformat(snap.params["acceptance"])
        for kpi, candidates in rules.items():
            matched: set[bool] = set()  # a release may give both quarterly and full-year guidance
            for i, rule in enumerate(candidates):
                is_annual = rule.get("period") == "annual"
                if is_annual in matched:
                    continue
                m = re.search(rule["pattern"], text, re.I)
                if not m:
                    continue
                matched.add(is_annual)
                g = m.groupdict()
                if g.get("qual"):
                    # Worded ranges ("up mid-teens", "low to mid-single digit") map to conventional ranges.
                    lo_n, hi_n = worded_range(g["qual"], g["band"], g.get("qual2"))
                    lo, hi = _signed(str(lo_n), g.get("lo_dir")), _signed(str(hi_n), g.get("lo_dir"))
                    if lo > hi:
                        lo, hi = hi, lo
                else:
                    lo = _signed(g.get("lo"), g.get("lo_dir"))
                    hi = _signed(g.get("hi"), g.get("hi_dir") or g.get("lo_dir"))
                kind = rule.get("period", "release_quarter")
                if kind == "explicit":
                    period = f"20{g['yy']}Q{g['q']}"
                elif kind == "named_quarter":  # "Third quarter comparable sales ..." in that year's release
                    period = f"{accepted.year}Q{_ORDINAL_Q[g['qname'].lower()]}"
                elif kind == "annual":  # full-year guidance; turned into implied quarters by implied_quarterly()
                    period = f"{accepted.year}FY"
                else:
                    period = period_of(accepted.date(), freq)
                out.append(ExternalForecast(
                    entity_id=entity_id, period=period, kpi=kpi, source="guidance", value=(lo + hi) / 2,
                    available_at=accepted,
                    source_ref=f"SEC {snap.params['accession']} {snap.params['document']} | {snapshot_ref(snap)} "
                               f"| rule {i}{' (worded range read as %s to %s)' % (lo, hi) if g.get('qual') else ''} "
                               f"| span: {m.group(0)!r}",
                ))
    return out


def implied_quarterly(annual: list[ExternalForecast], reported: dict[str, GroundTruth],
                      explicit: set[tuple[str, datetime]]) -> list[ExternalForecast]:
    """Full-year guidance A for year Y, issued after some of Y's quarters were reported, implies the
    remaining quarters average (4A - sum of reported) / remaining. Uses only quarters reported before
    the guidance was published (point in time). Skips quarters that the same release guided explicitly.
    Assumes the annual figure is the simple average of the quarters (fine for year-over-year rates)."""
    out = []
    for a in annual:
        year = int(a.period[:4])
        quarters = [f"{year}Q{q}" for q in range(1, 5)]
        known = {p: reported[p] for p in quarters if p in reported and reported[p].available_at <= a.available_at}
        remaining = [p for p in quarters if p not in known]
        if not remaining:
            continue
        implied = (4 * a.value - sum(g.value for g in known.values())) / len(remaining)
        for p in remaining:
            if (p, a.available_at) in explicit:
                continue
            parts = " + ".join(f"{k} {g.value:+.1f}" for k, g in sorted(known.items())) or "none reported"
            out.append(ExternalForecast(
                entity_id=a.entity_id, period=p, kpi=a.kpi, source=a.source, value=implied, available_at=a.available_at,
                source_ref=f"implied from FY guidance {a.value:+.2f}: (4 x {a.value:+.2f} - [{parts}]) / {len(remaining)} "
                           f"| {a.source_ref}"))
    return out
