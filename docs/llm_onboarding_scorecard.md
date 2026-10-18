# Portfolio scorecard

Generated 2026-10-18 06:06 UTC by `scripts/make_twin.py`. Walk-forward from 2017Q1, refit at every earnings release on data available at that moment. COVID quarters (2020Q1-2021Q4), plus any regime break a spec excludes from calibration (travel: through 2022Q4), are excluded from scoring. Factory twins use industry-pack defaults with no per-company tuning. Build time (s) is shown when the twin was built in this run; factory builds took 17-209 s on 2026-10-01, mostly waiting on rate limits. CRPS skill = 1 - CRPS(twin) / CRPS(baseline): positive means the twin is better.

| Ticker | Industry | Built by | Build s | Signals | Quarters | KPI | MAE twin | MAE naive | MAE seasonal | Skill vs naive | Skill vs seasonal | 80% coverage |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| UAL | airlines | factory+llm | 21 | 7 | 26 | revenue_growth | 3.79 | 4.13 | 17.22 | +0.45 | +0.81 | 0.81 |
| UAL | airlines | factory+llm | 21 | 7 | 26 | op_margin | 2.19 | 4.57 | 2.99 | +0.53 | +0.28 | 1.00 |
| UAL | airlines | factory+llm | 21 | 7 | 26 | fuel_pct_revenue | 1.21 | 1.91 | 3.38 | +0.37 | +0.58 | 0.92 |
| UAL | airlines | factory+llm | 21 | 7 | 26 | labor_pct_revenue | 1.25 | 1.97 | 1.66 | +0.32 | +0.25 | 0.73 |
| MAR | hotels | factory+llm | 12 | 6 | 26 | revenue_growth | 4.91 | 4.11 | 19.96 | -0.13 | +0.71 | 0.92 |
| MAR | hotels | factory+llm | 12 | 6 | 26 | op_margin | 2.34 | 2.72 | 1.75 | +0.20 | +0.22 | 0.73 |
| SBUX | restaurants | factory+llm | 17 | 7 | 29 | revenue_growth | 6.33 | 5.04 | 10.72 | +0.06 | +0.43 | 0.81 |
| SBUX | restaurants | factory+llm | 17 | 7 | 29 | op_margin | 1.81 | 2.43 | 3.27 | +0.58 | +0.60 | 0.90 |
| SBUX | restaurants | factory+llm | 17 | 7 | 29 | store_operating_expense_pct_revenue | 0.16 | 0.13 | 0.22 | -0.23 | +0.25 | 0.86 |
| SBUX | restaurants | factory+llm | 17 | 7 | 29 | product_distribution_cost_pct_revenue | 5.23 | 0.65 | 1.24 | -0.14 | +0.31 | 0.81 |
| TGT | general_retail | factory+llm | 13 | 5 | 31 | revenue_growth | 2.90 | 3.08 | 6.11 | +0.01 | +0.47 | 0.81 |
| TGT | general_retail | factory+llm | 13 | 5 | 31 | op_margin | 1.14 | 1.27 | 1.68 | -0.05 | +0.26 | 0.90 |
| TGT | general_retail | factory+llm | 13 | 5 | 31 | sga_expense_ratio | 0.85 | 1.29 | 0.81 | +0.36 | -0.02 | 0.74 |
| TGT | general_retail | factory+llm | 13 | 5 | 31 | cogs_ratio | 1.52 | 1.98 | 1.07 | +0.38 | +0.05 | 0.77 |

Twin beats naive (CRPS) on 10 of 14 KPI series.
