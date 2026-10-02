"""Backfill a twin's data from its spec: signals via the adapter registry, ground truth via EDGAR.

    python scripts/ingest.py specs/cmg.yaml --signals --ground-truth
    python scripts/ingest.py specs/cmg.yaml --ground-truth --reparse   # rerun parsers on saved raw files only

Raw responses land in data/raw/ before parsing; normalized rows go to data/chui.sqlite.
"""

from __future__ import annotations

import argparse
import re

import yaml
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adapters import adapter_for  # noqa: E402
from adapters.edgar import DOCUMENT_PATTERN, EdgarAdapter, extract_ground_truth, extract_guidance, filings, xbrl_ground_truth  # noqa: E402
from adapters.http import load_snapshots  # noqa: E402
from engine.spec import load_spec  # noqa: E402
from engine.observation import ExternalForecast  # noqa: E402
from storage import db  # noqa: E402


def ingest_signals(rspec, conn, start: date, end: date) -> None:
    for sig in rspec.signals:
        adapter = adapter_for(sig.series)
        try:
            snaps = adapter.fetch(adapter.params_for_series(sig.series), start, end)
        except Exception as e:  # keep going; one broken source must not stop the rest
            print(f"  FAIL {sig.series}: {e}")
            continue
        obs = [o for o in adapter.normalize(snaps) if o.series == sig.series]
        db.save_snapshots(conn, snaps)
        db.save_observations(conn, obs)
        span = f"{min(o.observed_at for o in obs)} .. {max(o.observed_at for o in obs)}" if obs else "none"
        print(f"  {sig.series:32s} {len(obs):6d} obs  {span}")


def ingest_xbrl(rspec, conn, reparse: bool) -> None:
    cfg = rspec.ground_truth["xbrl"]
    cik = str(int(cfg["cik"]))
    cached = sorted((s for s in load_snapshots("edgar") if s.params.get("kind") == "companyfacts"
                     and s.params.get("cik") == cik), key=lambda s: s.fetched_at)
    snap = cached[-1] if reparse and cached else EdgarAdapter().fetch_companyfacts(cik)
    db.save_snapshots(conn, [snap])
    rows = xbrl_ground_truth(snap, rspec.ticker, rspec.period, cfg["rules"])
    db.save_ground_truth(conn, rows)
    for kpi in cfg["rules"]:
        ps = sorted(r.period for r in rows if r.kpi == kpi)
        print(f"  xbrl {kpi:16s} {len(ps):3d} periods  {ps[0] if ps else '-'} .. {ps[-1] if ps else '-'}")


def ingest_ground_truth(rspec, conn, start: date, reparse: bool) -> None:
    # Ground truth is always rebuilt from raw snapshots, so stale parses never linger.
    conn.execute("DELETE FROM ground_truth WHERE entity_id = ?", (rspec.ticker,))
    conn.commit()
    if "xbrl" in rspec.ground_truth:
        ingest_xbrl(rspec, conn, reparse)
    manual = rspec.ground_truth.get("manual_external", [])
    cfg = rspec.ground_truth.get("edgar")
    if cfg:
        ingest_edgar(rspec, conn, start, reparse, cfg)
    for path in manual:
        ingest_manual_external(rspec, conn, ROOT / path)


def ingest_manual_external(rspec, conn, path: Path) -> None:
    """Hand-entered external forecasts (e.g. consensus from news coverage), each with URL and quote.
    'available: before_release' dates a row 1 hour before that period's first reported KPI."""
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    gt = db.load_ground_truth(conn, rspec.ticker)
    release = {}
    for g in gt:
        release[g.period] = min(release.get(g.period, g.available_at), g.available_at)
    rows = []
    for r in cfg["rows"]:
        if "available_at" in r:
            when = datetime.fromisoformat(str(r["available_at"]))
        elif cfg.get("available") == "before_release" and r["period"] in release:
            when = release[r["period"]] - timedelta(hours=1)
        else:
            continue  # not yet reported: no release to date it against; enter available_at explicitly
        rows.append(ExternalForecast(
            entity_id=cfg["entity_id"], period=r["period"], kpi=r.get("kpi", cfg["kpi"]), source=cfg["source"],
            value=float(r["value"]), available_at=when,
            source_ref=f"{r['url']} (published {r['published']}) | quote: {r['quote']!r} | file: {path.name}"))
    conn.execute("DELETE FROM external_forecasts WHERE entity_id = ? AND source = ?", (cfg["entity_id"], cfg["source"]))
    db.save_external(conn, rows)
    print(f"  {cfg['source']}: {len(rows)} hand-entered rows from {path.name}")


def ingest_edgar(rspec, conn, start: date, reparse: bool, cfg: dict) -> None:
    cik = str(int(cfg["cik"]))
    cached = [s for s in load_snapshots("edgar") if s.params.get("cik") == cik]
    if not reparse:
        edgar = EdgarAdapter()
        subs = edgar.fetch_submissions(cik)
        # Cached = documents saved, or an HTML index already checked by type and found none.
        have = {s.params.get("accession") for s in cached if s.params.get("kind") in ("document", "index_html")}
        extra = set(cfg.get("include_accessions", []))
        wanted = filings(subs, cfg.get("forms", ["8-K"]), cfg.get("items"))
        wanted += [f for f in filings(subs, cfg.get("forms", ["8-K"])) if f.accession in extra]
        todo = [f for f in wanted if date.fromisoformat(f.filing_date) >= start and f.accession not in have]
        print(f"  {len(todo)} filings to fetch ({len(have)} cached)")
        for f in todo:
            cached += edgar.fetch_documents(f, cfg.get("document_pattern", DOCUMENT_PATTERN))
        db.save_snapshots(conn, subs)
    pattern = cfg.get("document_pattern", DOCUMENT_PATTERN)
    typed = {s.params["accession"] for s in cached if s.params.get("kind") == "index_html"}
    docs = [s for s in cached if s.params.get("kind") == "document"
            and (re.search(pattern, s.params["document"], re.I) or s.params["accession"] in typed)]
    rows, report = extract_ground_truth(docs, rspec.ticker, rspec.period, cfg.get("rules", {}))

    # Several exhibits can describe one period (e.g. a later restatement); keep the first release.
    first: dict[tuple[str, str], object] = {}
    for g in sorted(rows, key=lambda g: g.available_at):
        first.setdefault((g.period, g.kpi), g)
    db.save_ground_truth(conn, list(first.values()))

    if cfg.get("guidance"):
        ext = extract_guidance(docs, rspec.ticker, rspec.period, cfg["guidance"])
        conn.execute("DELETE FROM external_forecasts WHERE entity_id = ? AND source = 'guidance'", (rspec.ticker,))
        db.save_external(conn, ext)
        print(f"  guidance: {len(ext)} rows, periods {sorted({e.period for e in ext})}")

    periods = sorted({r["period"] for r in report if r["period"]})
    found = Counter(k for (p, k) in first)
    print(f"  {len(docs)} exhibits, {len(periods)} periods detected ({periods[0] if periods else '-'} .. {periods[-1] if periods else '-'})")
    for kpi in cfg.get("rules", {}):
        missing = [p for p in periods if (p, kpi) not in first]
        print(f"  {kpi:14s} {found[kpi]:3d}/{len(periods)}  missing: {missing[:12]}{' ...' if len(missing) > 12 else ''}")
    undated = [r["accession"] for r in report if not r["period"]]
    if undated and cfg.get("rules"):
        print(f"  exhibits with no detectable period: {undated}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--signals", action="store_true")
    ap.add_argument("--ground-truth", action="store_true")
    ap.add_argument("--reparse", action="store_true", help="parse saved raw EDGAR files without fetching")
    ap.add_argument("--start", default="2012-01-01")
    args = ap.parse_args()

    rspec = load_spec(args.spec, ROOT / "templates")
    conn = db.connect()
    start, end = date.fromisoformat(args.start), date.today() + timedelta(days=1)
    if args.signals:
        print(f"[{rspec.ticker}] signals")
        ingest_signals(rspec, conn, start, end)
    if args.ground_truth:
        print(f"[{rspec.ticker}] ground truth")
        ingest_ground_truth(rspec, conn, start, args.reparse)


if __name__ == "__main__":
    main()
