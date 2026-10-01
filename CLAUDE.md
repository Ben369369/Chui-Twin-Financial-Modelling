# Chui Twin

A system that turns any public company into a runnable operating model. Public and scraped data are treated as noisy sensors of hidden operating states. A shared engine estimates those states, simulates them forward with Monte Carlo, attributes every output to its sources, and scores each twin against baselines.

Built for the Longaeva AI Hackathon. Chipotle (CMG) is the deep example. Delta (DAL) is the second twin, in a different industry, to prove the system transfers. The judges want a scalable system, not a single-company case study.

## Deadlines

- Oct 5-6: midpoint check-in with mentor. Need fitted CMG states and a first backtest.
- Oct 9: Stage 2 submission. CMG twin complete, DAL twin running, engine company-agnostic.
- Oct 21: finals. LLM onboarding, third twin, shock library, live demo.
- Oct 28: CMG reports Q3 after the close. Sealed forecast resolves.

## Non-negotiable rules

1. **The engine never contains company-specific or industry-specific code.** No tickers, no primitive names, no "restaurant" logic, no hardcoded series names in `engine/`. Industry structure lives in `templates/<name>.yaml`, company details in `specs/<ticker>.yaml`. If a feature needs company or industry code in the engine, stop and ask.
2. **Every number is traceable.** Every observation, ground-truth value and forecast carries a `source_ref` (URL, filing accession number plus exhibit, or raw snapshot path).
3. **Point-in-time correctness.** Every observation stores `observed_at` (the period it describes) and `available_at` (when it could first have been known). Backtests may only use rows where `available_at <= as_of_date`. This prevents lookahead bias, which would make the backtest look better than reality.
4. **Raw first, parse later.** Every fetch or scrape saves the untouched response to `data/raw/<source>/<YYYY-MM-DD>/` before parsing. Parsers can be fixed and rerun; missed scrape days cannot be recovered.
5. **Legal data only.** Check robots.txt and terms before building any scraper. No login-gated content. Log every source in `provenance.md` (source, license or terms, access method, what it informs).
6. **Ask before large refactors.** Propose a plan first for any change touching more than three files.

## Architecture

```
chui-twin/
  CLAUDE.md
  provenance.md
  docs/
    coverage_and_roadmap.md   # submission doc: where the system fits and the expansion order
  docker-compose.yml          # postgres + api + web
  pyproject.toml
  engine/                     # company-agnostic, never imports from specs directly
    primitives.py             # the state primitive definitions
    spec.py                   # loads and validates specs/*.yaml (pydantic)
    estimation/               # latent state estimation (weighted signals v0, Kalman v1)
    simulation/               # vectorized NumPy Monte Carlo
    attribution/              # driver waterfall + leave-one-signal-out counterfactuals
    evaluation/               # walk-forward backtest, baselines, CRPS, interval coverage
  adapters/                   # one module per data source, reusable across companies
    base.py
    edgar.py
    google_trends.py
    gdelt.py
    bls.py
    usda_ams.py
    eia.py
    tsa.py
    wikimedia.py
    scrapers/
      chipotle_locator.py
      chipotle_menu.py
      chipotle_careers.py
  templates/                  # industry templates: primitives, default edges, KPI structure
    operating.yaml
    _dummy.yaml               # test-only template with made-up primitive names
  specs/
    cmg.yaml
    dal.yaml
  onboarding/                 # LLM drafts a spec from a 10-K (finals milestone)
  prompts/                    # versioned LLM prompts, one file per task
  api/                        # FastAPI
  web/                        # React + Vite + Recharts + Tailwind
  scripts/
    run_daily.py              # runs all scheduled scrapers and fetchers
  data/raw/                   # gitignored
  tests/
```

## Industry templates and state primitives

Primitives are not hardcoded in the engine. They come from an **industry template** in `templates/<name>.yaml`. A template defines the primitive set, default causal edges with priors, and default KPI structure for a class of businesses. A company spec picks a template and overrides what it needs.

The engine only knows that a template has named primitives, edges between them, and KPIs built from them. It never references a primitive by name. Adding a new industry means adding a template file, not engine code.

Default template `operating` (restaurants, retail, airlines, hotels, homebuilders, transport):

| Primitive | Meaning |
|---|---|
| demand | underlying customer demand or volume |
| capacity | ability to serve demand (stores, seats, flights, units) |
| price | realized price per unit |
| input_cost | cost of goods, commodities, fuel |
| labor | wage and staffing pressure |
| sentiment | brand trust, safety events, public attention |
| expansion | new capacity pipeline |

Roadmap templates (do not build before Oct 9, but the engine must not prevent them):

- `bank`: deposits, loan_growth, credit_quality, net_interest_margin, funding_cost, sentiment. Signals from FFIEC call reports, Fed H.8, HMDA, CFPB complaints.
- `event`: for binary outcomes such as trial readouts or approvals. Outputs event probability and move size instead of a continuous path. Signals from ClinicalTrials.gov and FDA data. This needs an `engine/simulation/event.py` module that shares the attribution and evaluation code.

Test for this rule: `tests/test_template_agnostic.py` loads a dummy template with made-up primitive names and runs estimation and simulation end to end. If that test needs engine changes to pass, the engine is not agnostic.

## Adapter interface

Adapters know nothing about states or companies. They fetch data and return normalized observations. The spec maps series to primitives.

```python
class Adapter(ABC):
    source: str                                   # e.g. "google_trends"
    def fetch(self, params: dict, start: date, end: date) -> list[RawSnapshot]: ...
    def normalize(self, snapshots: list[RawSnapshot]) -> list[Observation]: ...

@dataclass
class Observation:
    entity_id: str        # ticker or "macro"
    source: str
    series: str           # e.g. "trends:chipotle", "ams:avocado_hass_48ct"
    observed_at: date
    available_at: datetime
    value: float
    unit: str
    geo: str | None
    source_ref: str
```

## Spec format

```yaml
ticker: CMG
name: Chipotle Mexican Grill
template: operating          # primitives and default edges come from templates/operating.yaml
industry: restaurant
period: quarter
kpis:
  comps: {formula: "transactions + check", unit: pct}
  transactions: {unit: pct}
  check: {unit: pct}
  rlom: {unit: pct}
primitives: [demand, capacity, price, input_cost, labor, sentiment, expansion]   # subset of the template's primitives
signals:
  - series: "trends:chipotle"
    primitive: demand
    sign: +1
    lag_days: 0
    confidence: 0.5
    half_life_days: 30
  - series: "ams:avocado_hass_48ct"
    primitive: input_cost
    sign: +1
    lag_days: 30
    confidence: 0.7
    half_life_days: 90
edges:                       # overrides or additions to template edges; causal graph fixed before looking at outcomes
  - {from: demand, to: transactions, prior_mean: 1.0, prior_sd: 0.3}
  - {from: sentiment, to: demand, prior_mean: 0.5, prior_sd: 0.2}
  - {from: price, to: check, prior_mean: 1.0, prior_sd: 0.1}
  - {from: price, to: demand, prior_mean: -0.3, prior_sd: 0.15}
baselines: [guidance, seasonal_naive, consensus]
```

## Database tables

- `raw_snapshots` (id, source, fetched_at, path, sha256, params)
- `observations` (fields from the Observation dataclass)
- `ground_truth` (entity_id, period, kpi, value, available_at, source_ref, confidence, verified)
- `states` (entity_id, as_of, primitive, mean, variance, run_id)
- `runs` (id, entity_id, as_of, spec_hash, scenario, n_paths, created_at)
- `forecasts` (run_id, kpi, period, p10, p50, p90, mean, sealed_at, sha256)

Use plain SQL migrations in `migrations/` numbered `001_init.sql` onward.

## Conventions

- Python 3.11, type hints everywhere, pydantic for specs and LLM outputs, pytest.
- Every adapter has a test using a saved fixture in `tests/fixtures/`, so tests never hit the network.
- SEC requests: User-Agent header "Benedict Ngetich <email>", at most 10 requests per second.
- Scrapers: identify with a descriptive User-Agent, at most 1 request every 2 seconds, retry with backoff, never bypass blocks or CAPTCHAs.
- LLM calls: model name from config (default `claude-sonnet-5-5`), JSON output validated with pydantic, prompts stored in `prompts/` with a version number, every extracted value keeps the source text span it came from.
- Monte Carlo: fully vectorized NumPy, target 10,000 paths in under 2 seconds.
- Keep the model simple. Judges reward data use and extensibility over model complexity.

## Coverage

See `docs/coverage_and_roadmap.md` for which industries the system fits, why, and the expansion order. Keep it updated as twins are added. It is part of the submission.

## Current focus

Week of Sep 30: scrapers running daily, CMG ground-truth table from EDGAR, public adapters (Trends, GDELT, BLS, USDA AMS, TSA), first state estimates.

## Implementation notes (added during build, Sep 30)

- Model math is documented in `docs/model.md`. Read it before changing estimation or simulation.
- Units: primitive states are standardized (mean 0, sd 1 over available history). Edge `prior_mean`/`prior_sd` are in standardized units: a one-sd move in the parent moves the child by `prior_mean` child-sd.
- `storage/` holds the SQLite store (dev). Migrations in `migrations/` are written in portable SQL so the same files run on Postgres. Docker is not installed on the dev machine yet.
- SEC User-Agent comes from env var `CHUI_SEC_USER_AGENT`, never hardcoded.
- Series names encode their query: `fred:<id>`, `wiki:<article>`, `tsa:checkpoint_throughput`. The adapter registry in `adapters/__init__.py` routes by prefix.
- `tests/test_engine_no_company_code.py` greps `engine/` for tickers, template primitive names and series prefixes. Keep it passing.
