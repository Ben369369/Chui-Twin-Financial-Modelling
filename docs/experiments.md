# Experiments

Signals and model changes that were tested and the result, including ones that did not help. A signal joins a
spec only if it improves the walk-forward backtest. Every experiment can be rerun from its script.

## 1. Hiring difficulty from JOLTS (2026-10-07): not adopted

**Question (office hours, Oct 6):** which public data best proxies hiring difficulty in the target sector?

**Setup.** The labor state is read only from average hourly earnings (BLS CES), which measure the price of
labor, not how hard it is to hire. We tested the standard hiring-difficulty measures from the BLS Job Openings
and Labor Turnover Survey (monthly, via FRED), one industry per twin:

| Twin | Quits rate | Job openings rate |
|---|---|---|
| CMG | `JTS7200QUR` (accommodation and food services) | `JTS7200JOR` |
| DAL | `JTU480099QUR` (transportation, warehousing, utilities; not seasonally adjusted) | `JTU480099JOR` |

Each series feeds the labor state with sign +1 (a tighter market means more labor pressure), confidence 0.4,
a 60-day half-life, and a year-over-year difference, which also removes the seasonality of the unadjusted
series. Walk-forward from 2017Q1 with the scorecard's exclusions (CMG 2020Q1–2021Q4, DAL 2020Q1–2022Q4).
Script: `scripts/experiments/jolts_labor.py`.

**Result.** Labor feeds only the margin KPIs, so revenue, comps and transactions are unchanged.

| KPI | Measure | Wages only | + quits | + openings | + both |
|---|---|---|---|---|---|
| CMG restaurant-level margin (30 q) | MAE | 1.77 | 1.73 | 1.79 | 1.76 |
| | CRPS skill vs last quarter | −0.09 | −0.10 | −0.08 | −0.10 |
| DAL operating margin (26 q) | MAE | **2.43** | 2.49 | 2.58 | 2.61 |
| | CRPS skill vs last quarter | **+0.36** | +0.36 | +0.35 | +0.35 |

**Reading.** No variant helps beyond noise, and DAL gets slightly worse. Three likely reasons:

1. Industry-wide hiring conditions are not company-specific. Chipotle and Delta manage labor cost through
   staffing and contracts that an industry quits rate does not see.
2. JOLTS moves with wage growth, which the state already uses, so it adds little new information.
3. With 26–30 scored quarters, a weak extra signal mostly adds estimation noise. This is the
   few-observations problem raised in office hours, and why the model stays simple.

**Decision.** JOLTS is not added to any spec. The better candidates are company-level postings data:
- Chipotle's own careers sitemap is already a low-confidence labor signal.
- Indeed Hiring Lab's public postings index by occupation is too short for a quarterly backtest: it starts
  in 2020, and COVID quarters are excluded.

## 2. LLM onboarding v1 (2026-10-18): adopted for coverage, not for accuracy

**Question.** Does an LLM reading the 10-K build a better twin than the rules-only factory?

**Setup.** `onboarding/llm.py` with prompt `prompts/onboard_spec_v1.md`, model `claude-sonnet-5-5`. The model
reads the latest 10-K and proposes a pack, extra driver series, extra XBRL KPIs, edge priors and operating
metrics, each with a quote from the filing. Code drops anything whose quote is not in the 10-K, whose series
cannot be fetched, whose XBRL concept lacks 16 quarters of history or is no longer reported, or whose state or KPI
is unknown. We ran it on four tickers that already have rules-only twins, one per industry, and rescored the
rules-only specs on the same day's data. Walk-forward from 2017Q1 with the scorecard's exclusions. Rerun with
`python scripts/make_twin.py UAL MAR SBUX TGT --llm --out specs/experiments/llm --scorecard docs/llm_onboarding_scorecard.md`.

**Result on the KPIs both versions share** (CRPS skill vs last quarter; positive is better):

| Twin | Revenue growth, rules | Revenue growth, + LLM | Op margin, rules | Op margin, + LLM |
|---|---|---|---|---|
| UAL (26 q) | +0.45 | +0.45 | +0.52 | +0.53 |
| MAR (26 q) | −0.07 | **−0.13** | +0.20 | +0.20 |
| SBUX (26/29 q) | +0.05 | +0.06 | +0.55 | **+0.58** (MAE 2.01 → 1.81) |
| TGT (31 q) | +0.01 | +0.01 | −0.05 | −0.05 |

**New KPIs the LLM added** (skill vs last quarter): UAL fuel share of revenue +0.37 and labor share +0.32;
TGT SG&A ratio +0.36 and cost-of-sales ratio +0.38; SBUX store operating expense −0.23 and product and
distribution cost −0.14 (MAE 5.23 against 0.65 for "last quarter").

**Reading.**
1. On the default KPIs the LLM changes almost nothing: its edge priors mostly confirm the pack defaults, and
   its extra drivers are weak signals. MAR revenue got slightly worse. We do not claim an accuracy gain.
2. Its value is coverage. It onboards companies no pack covers (Carnival, SIC 4400, has no pack; the model chose
   `hotels` and added airfares and jet fuel, with quotes), and it finds company-relevant KPIs that the
   twin forecasts better than naive (UAL, TGT).
3. It still needs review. On SBUX it listed two fallback concepts of different scope for one KPI, and one new
   KPI forecasts far worse than naive. New KPIs are therefore kept out of the portfolio scorecard until a person
   has checked them; `<ticker>.onboarding.json` lists every proposal, its quote and why rejected ones were dropped.
4. Hindsight: the model reads today's 10-K, and the backtest scores the resulting structure on earlier quarters,
   the same caveat as the pack choice. Its instructions forbid using known outcomes, but that cannot be verified.

**Decision.** Adopted as `make_twin.py --llm` for new tickers. Specs in `specs/experiments/llm/` stay out of the
portfolio. Carnival (`specs/auto/ccl.yaml`) is the first LLM-onboarded twin.
