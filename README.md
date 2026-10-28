# Chui Twin

Turns a public company into a runnable operating model. Public data (SEC filings, BLS, FRED, TSA,
news tone, Wikipedia attention, public sitemaps) is treated as noisy sensors of hidden operating
states (demand, capacity, price, input cost, labor, sentiment). One shared engine estimates those
states, simulates them forward with Monte Carlo, traces every forecast back to its sources, and
scores every twin the same way against naive, seasonal, guidance and consensus baselines.

Built for the Longaeva AI Hackathon (finals, October 2026).

## Run the demo

```bash
pip install numpy "pydantic>=2" pyyaml requests fastapi uvicorn anthropic
cd web && npm install && npm run build && cd ..
uvicorn api.serve:app --port 8000          # open http://localhost:8000
```

The chat panel and LLM onboarding (`make_twin.py --llm`) also need `ANTHROPIC_API_KEY` set.

The dashboard shows:
- **Portfolio:** every twin's walk-forward scorecard.
- **Twin** (`#/twin/CMG`, `#/twin/DAL`, ...): the forecast band against guidance, what moves each KPI (each bar links to its sources), the hidden states, and scenario sliders that push shocks through the causal graph.

The demo reads `data/chui.sqlite`. To rebuild it from scratch (raw responses are saved to `data/raw/` first):

```bash
export CHUI_SEC_USER_AGENT="Your Name you@example.com"   # SEC requires a contact
python scripts/ingest.py specs/cmg.yaml --signals --ground-truth
python scripts/ingest.py specs/dal.yaml --signals --ground-truth
python scripts/make_twin.py SBUX UAL MAR DHI WMT          # factory: ticker in, scored twin out
python scripts/make_twin.py --specs specs/*.yaml specs/auto/*.yaml --scorecard docs/portfolio_scorecard.md
```

## How it scales

| Layer | Shared by every twin | New company or industry needs |
|---|---|---|
| `engine/` | estimation, simulation, attribution, evaluation. A test fails if any ticker, primitive or series name appears here. | nothing |
| `adapters/` | SEC EDGAR + XBRL, FRED, BLS, TSA, Wikimedia, GDELT, sitemap counter with Wayback history | usually nothing |
| `templates/`, `onboarding/industry_packs.yaml` | primitives, causal edges with priors, the signals per industry | one YAML pack per industry |
| `onboarding/factory.py` | ticker → SEC SIC code → pack → spec; Wikipedia entity verified by ticker; KPIs from XBRL | the ticker |

## Results

Latest scorecard: `docs/portfolio_scorecard.md`.

- 17 twins on one engine: 2 hand-built, 14 built by the rules-only factory with no tuning, and Carnival onboarded by the LLM (`--llm`), which no industry pack covered.
- On CRPS, the twin beats both naive baselines on 24 of 37 KPI series: "same as last quarter" on 26 and "same quarter last year" on 35 (rescored 2026-10-19, after dating reported results at the earnings press release; see `provenance.md`).
- Against management guidance, the expectation each company publishes itself:
  - DAL revenue growth: CRPS skill +0.29 over 14 guided quarters; the twin was closer than Delta's guidance in 11 of 14 quarters (exact permutation test, p = 0.005).
  - CMG comps: CRPS skill +0.41 over 18 quarters.
  - Full comparisons, including analyst consensus, are in `docs/technical_appendix.md` §2 and `docs/surprise_direction.md`.

### Live test: sealed Q3 2026 forecasts

Each forecast was hashed and timestamped in Bitcoin (OpenTimestamps) before the company reported, then
scored against the earnings release. 6 of 7 KPIs landed inside the twin's 80% range.

| Twin | KPI | Sealed | Median (80% range) | Actual | Inside 80% |
|---|---|---|---|---|---|
| CMG | comps, yoy % | Oct 18 | 2.94 (0.64 to 5.15) | 2.1 | yes |
| CMG | transactions, yoy % | Oct 18 | 1.71 (−0.75 to 4.12) | 0.8 | yes |
| CMG | average check, yoy % | Oct 18 | 1.24 (0.05 to 2.41) | 1.3 | yes |
| CMG | restaurant-level margin, % | Oct 18 | 25.43 (20.97 to 29.97) | 23.3 | yes |
| CMG | revenue growth, yoy % | Oct 18 | 9.53 (−0.01 to 19.15) | 9.6 | yes |
| DAL | operating margin, % (GAAP) | Oct 2 | 6.9 (−1.8 to 15.6) | 7.2 | yes |
| DAL | revenue growth, yoy % (GAAP) | Oct 2 | 15.2 (10.6 to 19.9) | 21.1 | no |

- **CMG comps:** the median missed by 0.84 points. Guidance (2.65, implied from the full year) missed by 0.55,
  "same as last quarter" (2.2) by 0.1, and "same quarter last year" (0.3) by 1.8. The miss came from
  transactions: the largest driver of the sealed forecast was a July–August drop in news tone, which hit
  traffic less than the twin expected.
- **DAL revenue:** GAAP revenue includes third-party refinery sales, which rose 76% with fuel prices. Delta's
  guidance excludes them, and on that basis growth was 15.7%, 0.5 points from the twin's median. The twin had
  anchored a GAAP KPI on non-GAAP guidance; the scored result stays GAAP, as sealed.
- Sources: Chipotle 8-K accession 0001058090-26-000103 (EX-99.1, filed 2026-10-28); Delta 8-K accession
  0000027904-26-000035 (EX-99.1, filed 2026-10-09). Q4 2026 forecasts for both twins are sealed and pending.

Sealed out-of-sample forecasts and how to verify them: `docs/sealed_forecasts.md`.

**Start here for review:** `docs/technical_appendix.md` (method, evaluation, validation, limitations).
Data checks are in `docs/validation_report.md`, and tested-and-rejected signals in `docs/experiments.md`.

## Rules the code keeps

Every number carries a `source_ref` (filing accession and exhibit, URL plus quote, or raw snapshot
path). Backtests use only rows whose `available_at` precedes the forecast time. Every fetch is saved
raw before parsing. Only legal, public sources are used, and each is logged in `provenance.md`.
Details: `CLAUDE.md`, model math in `docs/model.md`, coverage in `docs/coverage_and_roadmap.md`.
