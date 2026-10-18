# Chui Twin: Coverage and Roadmap

## Where the system applies

Chui Twin models companies whose results are produced by observable operating drivers. A company is a strong fit when three conditions hold:

1. **Revenue decomposes into drivers.** Traffic times ticket, flights times load factor times fare, homes delivered times average price.
2. **Those drivers leave public traces between earnings reports.** Search interest, posted prices, job listings, permits, flight tracking, checkpoint counts.
3. **The business changes gradually enough to simulate.** Shocks propagate through operations over weeks and months rather than arriving as a single binary event.

The engine itself is industry-agnostic. Industry structure lives in templates, and company detail lives in spec files. Extending coverage means adding a template or a spec, not changing the engine.

## Coverage map

| Fit | Industries | Example signals from the Longaeva dataset list | Template |
|---|---|---|---|
| Strong | Restaurants, retail, airlines, hotels, homebuilders, cruise lines, trucking, rail | TSA checkpoint counts, Google Trends, Census MRTS, BTS T-100 and DB1B, Census permits and starts, USDA AMS, EIA fuel, BLS wages | `operating` (built) |
| Good with added work | Energy producers, semiconductors, consumer apps and gaming, streaming | EIA production, Baker Hughes rigs, WSTS, app store rankings, Steam Charts, Nielsen Top 10 | `operating` with new adapters |
| Weak | Enterprise software, conglomerates, large pharma | GitHub activity, H-1B filings, Medicare Part D spending | `operating`, low confidence |
| Needs a new template | Banks, insurers | FFIEC call reports, Fed H.8, HMDA, CFPB complaints, NAIC filings | `bank` (roadmap) |
| Needs a new engine module | Clinical-stage biotech, event-driven names | ClinicalTrials.gov, Drugs@FDA, FDA advisory calendars | `event` (roadmap) |

## Current state (updated October 18)

- **17 twins** (restaurants, airlines, hotels, homebuilders, general retail, and a cruise line) on one engine. 14 were built by the rules-only twin factory from the ticker alone, with no per-company tuning; Carnival was onboarded by the LLM because no industry pack covers its SIC code.
- **Engine:** state estimation, Monte Carlo simulation with scenario shocks, driver waterfall, leave-one-signal-out attribution, walk-forward evaluation, and sealed forecasts. Shared by every twin. Each KPI can be modeled as a level (with last-quarter and same-quarter-last-year terms), as a change since the last report, or as a surprise relative to guidance or consensus. Accounting identities and physical bounds are enforced on every simulated path.
- **Hand-built twins:**
  - Chipotle: 59 quarters of comps, transactions, check and margin extracted from earnings releases; store count and job postings from public sitemaps, with history from the Internet Archive; news tone; macro signals; consensus from public news quotes.
  - Delta: GAAP KPIs from XBRL; TSA throughput, jet fuel and airfare CPI; management guidance extracted from releases.
- **Twin factory (onboarding v0):** `scripts/make_twin.py <TICKER>` resolves the company at SEC, picks an industry pack by SIC code, attaches shared industry signals plus the company's verified Wikipedia article and news query, pulls KPIs from XBRL, and backtests.
- **Evaluation:** beats "last quarter" on 25 of 37 KPI series and "same quarter last year" on 35 of 37; beats management guidance on Delta revenue and Chipotle comps; trails analyst consensus on Chipotle comps. See `docs/portfolio_scorecard.md`.
- **Shock library:** half-lives measured from real events (Chipotle 2015 food safety, COVID, the Delta 2024 outage) feed the scenario presets.
- **Validation:** automatic checks on all 2,564 reported values (0 failures), plus a manual sample (`docs/validation_report.md`). Experiments, including the ones that failed, are in `docs/experiments.md`.
- **Live test:** the Delta Q3 forecast was sealed and timestamped in Bitcoin before the release. Chipotle's is sealed before Oct 28.

## Expansion order

1. **LLM-assisted onboarding (done, Oct 18).** `make_twin.py <TICKER> --llm`: an LLM reads the latest 10-K and proposes the pack, extra drivers, XBRL KPIs and edge priors, each with a quote; code drops anything it cannot verify. It onboarded Carnival, whose SIC code no pack covers. On four existing twins it left the shared KPIs about unchanged and added new KPIs that beat naive for UAL and TGT (`docs/experiments.md` §2). Next: turn its suggested operating metrics (comps, RevPAR, occupancy) into release-extraction rules checked by the validator.
2. **Filing tone and themes (by finals).** Keyword scoring with a finance word list plus LLM theme extraction on earnings releases, run several times so agreement across runs gives a confidence score. Adopted only if it improves the backtest.
3. **Company-level labor signals.** Industry hiring data (JOLTS) did not help; company postings data is the next candidate.
4. **Remaining strong-fit industries.** Cruise lines and freight reuse existing adapters, so each new company is mostly a spec file.
5. **`bank` template.** New primitives and adapters for balance-sheet businesses, with the same engine.
6. **`event` module.** Probability and move-size outputs for binary catalysts, sharing the attribution and evaluation code.

## Why it scales

The number of data adapters grows slowly while the number of companies they serve grows quickly. TSA data serves every airline. SEC XBRL, FRED, BLS, GDELT and Wikimedia serve every company. Each new twin mostly reuses adapters that already exist, adds one spec file, and is scored by the same evaluation harness, so twins stay comparable across a portfolio.

## Known limits

- Signal quality varies by company. Every twin reports its own backtest scorecard so users can see which twins are reliable.
- Causal edge strengths are set from priors and calibrated on limited quarterly history. They are validated, not discovered.
- Scraped signals depend on websites that can change. Raw snapshots are stored so parsers can be repaired and rerun.
