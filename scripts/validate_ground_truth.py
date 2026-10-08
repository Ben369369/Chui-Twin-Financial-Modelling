"""Validate extracted ground truth: automatic checks on every row, a small random sample for a person.

    python scripts/validate_ground_truth.py                   # checks + docs/validation_report.md + sample
    python scripts/validate_ground_truth.py --apply           # mark rows ticked "y" in the sample as verified

Automatic checks (every row):
  1. span:     a value extracted from text keeps its source span. The span must appear verbatim in the
               saved raw document, and the number in it (signed by its wording) must equal the value.
  2. identity: reported values must satisfy the spec's identities (e.g. comps = transactions + check),
               within the rounding of the published components.
  3. bounds:   values must sit inside the spec's physical bounds.
  4. outlier:  values more than 4 sd from the KPI's own history are flagged for review, not failed.

Manual review: a fixed-seed random sample of rows goes to docs/validation_sample.md with its source link.
A person checks each against the filing and writes y or n in the last column; --apply records the y rows
as verified in the ground_truth table. Automation covers every row; people review the sample and the flags.
"""

from __future__ import annotations

import argparse
import random
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters.edgar import html_to_text  # noqa: E402
from engine.spec import load_spec  # noqa: E402
from storage import db  # noqa: E402
from storage.db import data_root  # noqa: E402

REPORT = ROOT / "docs" / "validation_report.md"
SAMPLE = ROOT / "docs" / "validation_sample.md"
SAMPLE_SIZE = 20
IDENTITY_TOL = 0.6  # components are often published rounded to whole points ("a 7% increase")
NEGATIVE = re.compile(r"decreas|declin|\bdown\b|\bfell\b|negative|\blower\b|\bfewer\b", re.I)


def span_values(span: str) -> list[float]:
    """Every number in the span, signed by the wording of its own clause."""
    if re.search(r"\bflat\b", span, re.I):
        return [0.0]
    out = []
    for clause in re.split(r",|;|\band\b", span):
        sign = -1.0 if NEGATIVE.search(clause) else 1.0
        for m in re.finditer(r"(\()?(-?\d+(?:\.\d+)?)\)?", clause):
            v = float(m.group(2))
            out.append(-abs(v) if m.group(1) else sign * abs(v) if v >= 0 else v)
    return out


_text_cache: dict[str, str] = {}


def raw_text(rel: str) -> str | None:
    if rel not in _text_cache:
        p = data_root() / rel
        _text_cache[rel] = html_to_text(p.read_bytes()) if p.exists() else None
    return _text_cache[rel]


def check_span(g) -> str | None:
    """None if the row has no text span; "" if it passes; otherwise the failure."""
    m = re.search(r"span: '(.*)'\s*$", g.source_ref)
    raw = re.search(r"raw:(\S+)", g.source_ref)
    if not m:
        return None
    span = m.group(1)
    if raw is None:
        return "span without a raw snapshot path"
    text = raw_text(raw.group(1))
    if text is None:
        return f"raw file missing: {raw.group(1)}"
    if " ".join(span.split()) not in text:
        return "span not found verbatim in the raw document"
    vals = span_values(span)
    if not any(abs(v - g.value) <= 0.051 for v in vals):
        return f"span says {vals}, stored value is {g.value}"
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="record rows marked y in the sample as verified")
    args = ap.parse_args()
    conn = db.connect()

    if args.apply:
        n = 0
        for line in SAMPLE.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 6 and cells[-1].lower() == "y":
                n += conn.execute("UPDATE ground_truth SET verified = 1 WHERE entity_id=? AND period=? AND kpi=?",
                                  (cells[0], cells[1], cells[2])).rowcount
        conn.commit()
        print(f"marked {n} rows verified")
        return

    paths = sorted((ROOT / "specs").glob("*.yaml")) + sorted((ROOT / "specs" / "auto").glob("*.yaml"))
    specs = {}
    for p in paths:  # hand-built specs win over auto specs for the same ticker
        r = load_spec(p, ROOT / "templates")
        specs.setdefault(r.ticker, r)

    counts = defaultdict(lambda: defaultdict(int))
    problems: list[tuple[str, str, str, str]] = []
    flags: list[tuple[str, str, str, str]] = []
    all_rows = []
    for ticker, rspec in sorted(specs.items()):
        rows = db.load_ground_truth(conn, ticker)
        all_rows += rows
        by = {(g.period, g.kpi): g.value for g in rows}
        for g in rows:
            res = check_span(g)
            if res is not None:
                counts[ticker]["span checked"] += 1
                if res:
                    problems.append((ticker, g.period, g.kpi, res))
            kdef = rspec.kpis.get(g.kpi)
            lo, hi = (kdef.bounds if kdef is not None and kdef.bounds else (None, None))
            if (lo is not None and g.value < lo) or (hi is not None and g.value > hi):
                problems.append((ticker, g.period, g.kpi, f"value {g.value} outside bounds [{lo}, {hi}]"))
            counts[ticker]["rows"] += 1
        for kpi in {g.kpi for g in rows}:
            vals = [g.value for g in rows if g.kpi == kpi]
            if len(vals) < 8:
                continue
            med, sd = statistics.median(vals), statistics.pstdev(vals)
            for g in rows:
                if g.kpi == kpi and sd and abs(g.value - med) > 4 * sd:
                    flags.append((ticker, g.period, kpi, f"{g.value} is {abs(g.value - med) / sd:.1f} sd from the median"))
        for ident in rspec.identities:
            for period in sorted({p for p, _ in by}):
                if all((period, k) in by for k in ident.coefs):
                    counts[ticker]["identity checked"] += 1
                    r = ident.residual({k: by[(period, k)] for k in ident.coefs})
                    if abs(r) > IDENTITY_TOL:
                        problems.append((ticker, period, ident.text, f"residual {r:+.2f}"))

    total = sum(c["rows"] for c in counts.values())
    lines = ["# Ground-truth validation", "",
             "Generated by `scripts/validate_ground_truth.py`. Automatic checks run on every row; a random sample "
             "goes to people (`docs/validation_sample.md`).", "",
             "| Twin | Rows | Text spans checked | Identity checks |", "|---|---|---|---|"]
    lines += [f"| {t} | {c['rows']} | {c['span checked']} | {c['identity checked']} |" for t, c in sorted(counts.items())]
    lines += ["", f"**{total} rows. {len(problems)} failed a check; {len(flags)} flagged as outliers for review.** "
              f"{sum(g.verified for g in all_rows)} rows are verified by a person so far.", ""]
    lines += ["## Failures", ""] + ([f"- {t} {p} {k}: {m}" for t, p, k, m in problems] or ["None."])
    lines += ["", "## Outliers to review (not failures: real shocks such as COVID show up here)", ""]
    lines += [f"- {t} {p} {k}: {m}" for t, p, k, m in flags] or ["None."]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if not SAMPLE.exists():
        rng = random.Random(20261007)
        pick = sorted(rng.sample(all_rows, min(SAMPLE_SIZE, len(all_rows))), key=lambda g: (g.entity_id, g.period, g.kpi))
        out = ["# Manual validation sample", "",
               "Open each source, find the number, and write y (matches) or n (does not) in the last column. "
               "Then run `python scripts/validate_ground_truth.py --apply`.", "",
               "Rows marked (XBRL) link the 10-Q or 10-K. Find the income statement: revenue growth is this "
               "quarter's total revenue over the same quarter a year earlier, minus 1, in percent; operating "
               "margin is operating income over total revenue. A Q4 value is the full year minus the first nine "
               "months, so check it against the 10-K. Small rounding differences (under 0.1) count as a match.", "",
               "| Twin | Period | KPI | Value | Source | Matches (y/n) |", "|---|---|---|---|---|---|"]
        for g in pick:
            url = next((u for u in re.findall(r"https?://\S+", g.source_ref)), "")
            accn, cik = re.search(r"accn:(\S+)", g.source_ref), re.search(r"CIK(\d+)", g.source_ref)
            if accn and cik:  # XBRL fact: link the filing a person can read, not the JSON
                url = f"https://www.sec.gov/Archives/edgar/data/{int(cik.group(1))}/{accn.group(1).replace('-', '')}/ (XBRL)"
            out.append(f"| {g.entity_id} | {g.period} | {g.kpi} | {g.value:.2f} | {url} | |")
        SAMPLE.write_text("\n".join(out) + "\n", encoding="utf-8")

    print(f"{total} rows, {len(problems)} failures, {len(flags)} outliers flagged -> {REPORT.relative_to(ROOT)}")
    for t, p, k, m in problems[:30]:
        print(f"  FAIL {t} {p} {k}: {m}")


if __name__ == "__main__":
    main()
