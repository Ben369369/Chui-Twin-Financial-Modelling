"""XBRL ground truth is dated at the earnings release, not the later 10-Q/10-K, so backtest forecasts precede it."""

from datetime import date, datetime, timezone

from adapters.edgar import Filing, first_release


def _release(day: str, accn: str) -> Filing:
    return Filing(cik="1", accession=accn, form="8-K", filing_date=day,
                  acceptance=datetime.fromisoformat(day + "T06:30:00+00:00"),
                  report_date=day, items="2.02,9.01", primary_document="x.htm")


RELEASES = [_release("2024-01-12", "q4-2023"), _release("2024-04-10", "q1-2024"), _release("2024-07-11", "q2-2024")]


def test_q4_is_dated_at_the_january_release_not_the_february_10k():
    rel = first_release(RELEASES, date(2023, 12, 31), filed=date(2024, 2, 12))
    assert rel is not None and rel.accession == "q4-2023"


def test_release_must_fall_between_period_end_and_the_filing():
    assert first_release(RELEASES, date(2024, 3, 31), filed=date(2024, 4, 11)).accession == "q1-2024"
    # a release after the filing cannot date the filing's numbers
    assert first_release(RELEASES, date(2024, 3, 31), filed=date(2024, 4, 9)) is None


def test_fiscal_quarter_end_is_used_not_the_calendar_quarter():
    # a retailer's quarter ending Nov 2 is reported on Nov 20; a calendar end (Dec 31) would miss it
    rel = first_release([_release("2024-11-20", "fq3")], date(2024, 11, 2), filed=date(2024, 12, 4))
    assert rel is not None and rel.acceptance == datetime(2024, 11, 20, 6, 30, tzinfo=timezone.utc)


def test_evening_release_matches_a_same_day_10q():
    # Starbucks, 2020-01-28: release accepted 21:12 ET (02:12 UTC on the 29th), 10-Q filed the same evening
    late = Filing(cik="1", accession="sbux", form="8-K", filing_date="2020-01-28",
                  acceptance=datetime(2020, 1, 29, 2, 12, tzinfo=timezone.utc), report_date="2020-01-28",
                  items="2.02,9.01", primary_document="x.htm")
    assert first_release([late], date(2019, 12, 29), filed=date(2020, 1, 28)) is late


def test_growth_against_a_negative_base_is_dropped():
    import json
    from adapters.edgar import xbrl_ground_truth
    from engine.observation import RawSnapshot

    def q(end, start, val, accn, filed):
        return {"start": start, "end": end, "val": val, "accn": accn, "filed": filed}
    facts = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
        q("2019-09-30", "2019-07-01", 100.0, "a1", "2019-10-25"),
        q("2020-09-30", "2020-07-01", -5.0, "a2", "2020-10-25"),   # net refunds exceed revenue
        q("2021-09-30", "2021-07-01", 60.0, "a3", "2021-10-25"),
        q("2022-09-30", "2022-07-01", 120.0, "a4", "2022-10-25"),
    ]}}}}}
    import adapters.edgar as edgar
    snap = RawSnapshot(source="edgar", fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc), path="x", sha256="0",
                       params={"kind": "companyfacts"})
    orig = edgar.read_raw
    edgar.read_raw = lambda s: json.dumps(facts).encode()
    try:
        rows = xbrl_ground_truth(snap, "TEST", "quarter", {"revenue_growth": {"kind": "yoy", "concepts": ["Revenues"]}})
    finally:
        edgar.read_raw = orig
    by = {r.period: r.value for r in rows}
    assert "2020Q3" not in by and "2021Q3" not in by       # into, and against, a negative value
    assert abs(by["2022Q3"] - 100.0) < 1e-9                  # 60 -> 120 is still +100%
