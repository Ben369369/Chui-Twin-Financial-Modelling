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

## Current state (October 9 submission)

- **Engine:** state estimation, Monte Carlo simulation, driver attribution, counterfactual attribution, walk-forward evaluation. Shared by every twin.
- **Template:** `operating`, with seven primitives (demand, capacity, price, input cost, labor, sentiment, expansion).
- **Twins:** Chipotle (restaurant, deep model with scraped menu prices, store openings and job postings) and Delta (airline, built on the same engine from a spec file).
- **Evaluation:** every twin is scored the same way against management guidance, a seasonal naive baseline and consensus, using forecast error, interval coverage and CRPS.

## Expansion order

1. **LLM-assisted onboarding (by finals).** Given a ticker, an LLM reads the latest 10-K, identifies KPIs and drivers, maps them to template primitives, selects signals from the adapter catalog and drafts a spec for human review. Target: a working twin with a backtest scorecard in under one hour.
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
