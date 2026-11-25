# Sealed forecasts

Each forecast is written to `forecasts/sealed/` as canonical JSON and identified by its SHA-256.
A hash proves nothing about *when* until it is timestamped independently. Each sealed file has an
OpenTimestamps proof beside it (`<file>.ots`), which anchors its SHA-256 in the Bitcoin blockchain
via public calendar servers. Nobody has to trust us.

- **Verify the hash:** `python -c "from engine.sealing import verify; print(verify('<path>'))"`
- **Verify the timestamp:** drop the `.json` and `.ots` files on https://opentimestamps.org, or run
  `python scripts/ots.py info <file>.ots`. `scripts/run_daily.py` upgrades pending proofs to full Bitcoin proofs.

| Sealed (UTC) | Twin | Forecast | Median | 80% range | Vs guidance | Resolves | SHA-256 |
|---|---|---|---|---|---|---|---|
| 2026-10-02 20:58 | DAL | 2026Q3 revenue growth, yoy % (GAAP) | 15.2 | 10.6 to 19.9 | guidance mid-teens (15.0); P(above) 53% | Delta Q3 release, ~Oct 9 | `f6892ab9366122fd81b64c1106b052c1962638c6ab8644587c5baee2d2058bd8` (OpenTimestamps: submitted 2026-10-02 21:13 UTC, anchored in Bitcoin block 969637) |
| 2026-10-18 19:00 | CMG | 2026Q3 comps, yoy % | 2.94 | 0.64 to 5.15 | guidance 2.65 (implied from full year); P(above) 57% | Chipotle Q3 release, Oct 28 after close | `fabe5e811fcf5fe2e0b909a5d7c7e6ff5e69a8ee691645214ec7e816c0016282` (OpenTimestamps: submitted 2026-10-18, anchored in Bitcoin block 972040) |
| (same file) | CMG | 2026Q3 transactions / check / restaurant-level margin / revenue growth | 1.71 / 1.24 / 25.43 / 9.53 | −0.75 to 4.12 / 0.05 to 2.41 / 20.97 to 29.97 / −0.01 to 19.15 | – | Oct 28 | same hash |
| 2026-11-25 02:49 | CMG | 2026Q4 comps, yoy % (re-seal after Q3) | 4.94 | 2.73 to 7.15 | guidance 3.20 (implied from full year); P(above) 85% | Chipotle Q4 release, ~Feb 2 | `3a4bc035a9c2eb5df1da32349251573028ef2ee1421a4b093435809394b5e3a7` (OpenTimestamps: submitted 2026-11-25) |
| (same file) | CMG | 2026Q4 transactions / check / restaurant-level margin / revenue growth | 3.55 / 1.41 / 23.21 / 10.96 | 1.16 to 5.91 / 0.27 to 2.55 / 18.84 to 27.70 / 1.43 to 20.59 | – | ~Feb 2 | same hash |
| 2026-11-25 02:49 | DAL | 2026Q4 revenue growth, yoy % (GAAP) / operating margin, % (re-seal after Q3) | 21.00 / 6.12 | 16.27 to 25.84 / −2.48 to 14.52 | – | Delta Q4 release, ~Jan 8–13 | `838cc0ae172409bbff92bcfba915aa742fa5d93fed6e332ed18e7bbd0367e803` (OpenTimestamps: submitted 2026-11-25) |

**Re-seals and automatic seals (from 2026-11-25).** The October files also cover 2026Q4, sealed before Q3 was known.
The Nov 25 files re-seal Q4 with Q3 in the data. The DAL re-seal still uses the GAAP-anchored revenue model described
under the DAL outcome below; the fix is not in it. From now on `scripts/auto_seal.py` (run by `run_daily.py`) seals
every twin (18 specs today) once per quarter, opening 10 days before the release expected from the company's own past release
dates. The rule for scoring, fixed before any of these resolve: when a period has several seals, the headline score is
the latest seal made before the release; every seal stays listed in `docs/sealed_results.md`.

**CMG data note (2026-10-18).** The largest driver of the sealed comps and transactions forecasts is a drop in
Chipotle news tone (GDELT) in July and August 2026; the sentiment state for Q3 is −1.16 sd. GDELT's own response
has no Chipotle tone for 2026-07-01..07-04, 09-14..09-19 and 09-26 (raw file
`data/raw/gdelt/2026-10-18/tone_chipotle_1b9fc10a4739.json`; refetched, still absent), so Q3 sentiment rests on
81 of 92 days. Sealed as is, two days before the submission deadline.

Outcomes are recorded here after the release, unchanged rows above, with the reported value and its SEC accession.
`python scripts/resolve_sealed.py` checks every hash, accepts an outcome only if it became public after the
seal, and scores the twin against guidance, last quarter and last year in `docs/sealed_results.md`. An outcome is
taken from the earnings release (8-K EX-99.1) on the day it is filed; the 10-Q's XBRL facts replace it later
with the same GAAP figures.

## Outcome: DAL 2026Q3 (resolved 2026-10-09)

Delta reported on 2026-10-09 at 10:30 UTC (8-K accession 0000027904-26-000035, EX-99.1). The sealed file's
hash verified, and the outcome was public only after the seal. Scored by `scripts/resolve_sealed.py`
(`docs/sealed_results.md`); lower CRPS is better, baselines are points.

| KPI | Sealed median (80% range) | Actual | Inside 80% | Twin CRPS | Guidance | Last quarter | Last year |
|---|---|---|---|---|---|---|---|
| Operating margin (GAAP) | 6.9 (−1.8 to 15.6) | **7.2** | yes | **1.60** | – | 2.23 | 2.90 |
| Revenue growth (GAAP) | 15.2 (10.6 to 19.9) | **21.1** | **no** | 3.93 | 6.07 | **2.40** | 14.72 |

- **Margin:** the twin was 0.3 points off and beat both naive baselines.
- **Revenue growth:** the twin beat Delta's guidance but missed high, outside its 80% range, and lost to
  "same as last quarter".
- **Why it missed:** GAAP operating revenue ($20,186M vs $16,673M) includes third-party refinery sales,
  which rose 76% ($2,601M vs $1,476M) with high fuel prices and added about 6.7 points of growth.
  Delta's guidance ("mid-teens") is for adjusted revenue excluding the refinery, which grew 15.7%, 0.5 points
  from the twin's median. The twin anchored a GAAP KPI on non-GAAP guidance. The scored result stays
  GAAP, as sealed.
- **Fix, for future forecasts and not applied to this one:** match the anchor's definition to the KPI.
  Either forecast adjusted revenue (GAAP minus refinery sales, both from the release) against guidance,
  or add refinery sales as a separate KPI driven by fuel prices.
- **Applied 2026-11-25, after the Nov 25 re-seal:** a new KPI, `revenue_growth_adj` (Delta's "Total Revenue,
  adjusted" growth from each release), is anchored on guidance, which is its own definition. GAAP
  `revenue_growth` keeps the guidance anchor as an approximate bar (unanchored scored worse in the backtest,
  CRPS 5.29 vs 4.67) and gains a weak fuel-cost link for refinery sales. Delta's new single-figure guidance
  ("4Q26 Total Revenue YoY (%) Approx. 20%") is now extracted; the Nov 25 seal had none for Q4. Seals from
  the next automatic run (window opens about Dec 29) include both KPIs.
