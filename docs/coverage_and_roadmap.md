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

## Current state (updated October 1)

- **Engine:** state estimation, Monte Carlo simulation with scenario shocks, driver waterfall, leave-one-signal-out attribution, and walk-forward evaluation. Shared by every twin. KPIs can be modeled as levels, with optional last-quarter and same-quarter-last-year terms, or as changes since the last report.
- **Template:** `operating`, with seven primitives (demand, capacity, price, input cost, labor, sentiment, expansion).
- **Hand-built twins:**
  - Chipotle: 59 quarters of comps and margin extracted from earnings releases; store count and job postings from public sitemaps, with history from the Internet Archive; news tone; macro signals.
  - Delta: GAAP KPIs from XBRL; TSA throughput, jet fuel and airfare CPI; management guidance extracted from releases.
- **Twin factory (onboarding v0):** `scripts/make_twin.py <TICKER>` resolves the company at SEC, picks an industry pack by SIC code, attaches shared industry signals plus the company's Wikipedia article and news query, pulls KPIs from XBRL, and backtests. No hand-written config. Packs exist for restaurants, airlines, hotels, homebuilders and general retail.
- **Evaluation:** every twin is scored the same way against naive (last quarter), seasonal naive and, where available, management guidance, using MAE, CRPS and 80% interval coverage. Results are in `docs/portfolio_scorecard.md`.

## Expansion order

1. **LLM-assisted onboarding (by finals).** The rule-based factory already turns a ticker into a scored twin in minutes. v1 adds an LLM that reads the latest 10-K, picks company-specific KPIs (comps, RevPAR, deliveries) and drivers beyond the pack defaults, and drafts the extraction rules for its earnings releases. Every extracted value keeps its source span.
2. **Third twin in a third industry (by finals).** A homebuilder, built mainly through onboarding, with the time taken recorded.
3. **Shock library (by finals).** Food-safety scares, fuel spikes, strikes and rate shocks, each with a measured decay profile reused as priors across companies.
4. **Remaining strong-fit industries.** Hotels, retail, cruise lines and freight reuse existing adapters, so each new company is mostly a spec file.
5. **`bank` template.** New primitives and adapters for balance-sheet businesses, with the same engine.
6. **`event` module.** Probability and move-size outputs for binary catalysts, sharing the attribution and evaluation code.

## Why it scales

The number of data adapters grows slowly while the number of companies they serve grows quickly. TSA data serves every airline. Google Trends, GDELT and BLS serve every company. Each new twin mostly reuses adapters that already exist, adds one spec file, and is scored by the same evaluation harness, so twins stay comparable across a portfolio.

## Known limits

- Signal quality varies by company. Every twin reports its own backtest scorecard so users can see which twins are reliable.
- Causal edge strengths are set from priors and calibrated on limited quarterly history. They are validated, not discovered.
- Scraped signals depend on websites that can change. Raw snapshots are stored so parsers can be repaired and rerun.
