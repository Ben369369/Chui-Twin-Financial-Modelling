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
