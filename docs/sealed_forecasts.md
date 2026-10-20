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
