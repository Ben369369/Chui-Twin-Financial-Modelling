# Portfolio scorecard

Generated 2026-10-19 22:04 UTC by `scripts/make_twin.py`. Walk-forward from 2017Q1, refit at every earnings release on data available at that moment. COVID quarters (2020Q1-2021Q4), plus any regime break a spec excludes from calibration (travel: through 2022Q4), are excluded from scoring. Factory twins use industry-pack defaults with no per-company tuning. Build time (s) is shown when the twin was built in this run; factory builds took 17-209 s on 2026-10-01, mostly waiting on rate limits. CRPS skill = 1 - CRPS(twin) / CRPS(baseline): positive means the twin is better.

| Ticker | Industry | Built by | Build s | Signals | Quarters | KPI | MAE twin | MAE naive | MAE seasonal | Skill vs naive | Skill vs seasonal | 80% coverage |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CMG | restaurant | hand | - | 9 | 30 | transactions | 3.30 | 2.55 | 7.10 | +0.19 | +0.75 | 0.67 |
| CMG | restaurant | hand | - | 9 | 30 | check | 1.23 | 0.77 | 1.07 | -0.10 | +0.46 | 0.69 |
| CMG | restaurant | hand | - | 9 | 30 | comps | 3.13 | 3.69 | 9.21 | +0.21 | +0.67 | 0.80 |
| CMG | restaurant | hand | - | 9 | 30 | rlom | 1.77 | 1.65 | 2.14 | -0.07 | +0.24 | 1.00 |
| CMG | restaurant | hand | - | 9 | 30 | revenue_growth | 3.86 | 3.92 | 9.48 | -0.06 | +0.56 | 0.97 |
| DAL | airline | hand | - | 6 | 27 | revenue_growth | 2.83 | 4.08 | 15.73 | +0.31 | +0.84 | 0.67 |
| DAL | airline | hand | - | 6 | 27 | op_margin | 2.32 | 4.93 | 2.77 | +0.36 | +0.01 | 1.00 |
| AAL | airlines | factory | - | 6 | 26 | revenue_growth | 3.85 | 3.80 | 14.60 | +0.09 | +0.75 | 0.96 |
| AAL | airlines | factory | - | 6 | 26 | op_margin | 2.61 | 5.68 | 4.18 | +0.49 | +0.36 | 0.85 |
| CCL | hotels | factory+llm | - | 7 | 27 | revenue_growth | 8.51 | 8.68 | 469.78 | +0.02 | +0.98 | 0.67 |
| CCL | hotels | factory+llm | - | 7 | 27 | op_margin | 9.65 | 10.54 | 11.15 | -0.06 | +0.21 | 0.70 |
| DHI | homebuilders | factory | - | 7 | 30 | revenue_growth | 4.89 | 5.07 | 9.35 | +0.13 | +0.52 | 0.90 |
| DHI | homebuilders | factory | - | 7 | 30 | pretax_margin | 1.20 | 1.36 | 2.22 | +0.10 | +0.46 | 0.97 |
| DRI | restaurants | factory | - | 6 | 31 | revenue_growth | 5.47 | 4.11 | 12.29 | -0.01 | +0.62 | 0.97 |
| DRI | restaurants | factory | - | 6 | 31 | op_margin | 2.18 | 2.02 | 0.92 | +0.10 | +0.02 | 1.00 |
| HLT | hotels | factory | - | 5 | 26 | revenue_growth | 4.73 | 4.55 | 14.30 | -0.05 | +0.67 | 0.88 |
| HLT | hotels | factory | - | 5 | 26 | op_margin | 2.11 | 3.06 | 1.71 | +0.30 | -0.11 | 0.96 |
| LEN | homebuilders | factory | - | 7 | 31 | revenue_growth | 9.52 | 9.27 | 19.69 | -0.06 | +0.52 | 0.81 |
| LEN | homebuilders | factory | - | 7 | 31 | op_margin | 3.38 | 3.75 | 4.17 | +0.18 | +0.18 | 0.69 |
| LUV | airlines | factory | - | 6 | 26 | revenue_growth | 3.19 | 3.37 | 12.82 | +0.07 | +0.78 | 0.85 |
| LUV | airlines | factory | - | 6 | 26 | op_margin | 4.08 | 4.70 | 2.75 | +0.09 | -0.41 | 0.73 |
| MAR | hotels | factory | - | 5 | 26 | revenue_growth | 4.73 | 4.11 | 19.96 | -0.07 | +0.72 | 0.92 |
| MAR | hotels | factory | - | 5 | 26 | op_margin | 2.34 | 2.72 | 1.75 | +0.20 | +0.23 | 0.77 |
| MCD | restaurants | factory | - | 6 | 30 | revenue_growth | 4.08 | 3.80 | 9.80 | -0.02 | +0.58 | 0.90 |
| MCD | restaurants | factory | - | 6 | 30 | op_margin | 3.46 | 3.56 | 4.14 | -0.01 | +0.15 | 0.93 |
| PHM | homebuilders | factory | - | 7 | 27 | revenue_growth | 4.74 | 4.45 | 11.56 | +0.33 | +0.60 | 0.96 |
| PHM | homebuilders | factory | - | 7 | 27 | pretax_margin | 2.32 | 2.46 | 2.59 | +0.68 | +0.55 | 0.96 |
| SBUX | restaurants | factory | - | 6 | 29 | revenue_growth | 6.32 | 5.04 | 10.72 | +0.06 | +0.43 | 0.81 |
| SBUX | restaurants | factory | - | 6 | 29 | op_margin | 2.00 | 2.43 | 3.27 | +0.55 | +0.58 | 0.90 |
| TGT | general_retail | factory | - | 5 | 31 | revenue_growth | 2.84 | 3.08 | 6.11 | +0.02 | +0.47 | 0.74 |
| TGT | general_retail | factory | - | 5 | 31 | op_margin | 1.11 | 1.22 | 1.61 | +0.01 | +0.26 | 0.90 |
| TXRH | restaurants | factory | - | 6 | 29 | revenue_growth | 4.84 | 4.15 | 7.74 | +0.12 | +0.52 | 0.93 |
| TXRH | restaurants | factory | - | 6 | 29 | op_margin | 1.26 | 1.52 | 1.25 | +0.08 | +0.03 | 0.93 |
| UAL | airlines | factory | - | 6 | 26 | revenue_growth | 3.83 | 4.13 | 17.22 | +0.45 | +0.81 | 0.81 |
| UAL | airlines | factory | - | 6 | 26 | op_margin | 2.19 | 4.57 | 2.99 | +0.52 | +0.27 | 1.00 |
| WMT | general_retail | factory | - | 5 | 31 | revenue_growth | 1.23 | 1.21 | 2.62 | -0.00 | +0.50 | 0.87 |
| WMT | general_retail | factory | - | 5 | 31 | op_margin | 0.44 | 0.58 | 0.52 | +0.15 | +0.16 | 0.87 |

Twin beats naive (CRPS) on 26 of 37 KPI series.
