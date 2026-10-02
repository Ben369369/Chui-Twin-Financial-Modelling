# Portfolio scorecard

Generated 2026-10-02 00:03 UTC by `scripts/make_twin.py`. Walk-forward from 2017Q1, refit at every earnings release on data available at that moment. COVID quarters (2020Q1-2021Q4), plus any regime break a spec excludes from calibration (travel: through 2022Q4), are excluded from scoring. Factory twins use industry-pack defaults with no per-company tuning. Build time (s) is shown when the twin was built in this run; factory builds took 17-209 s on 2026-10-01, mostly waiting on rate limits. CRPS skill = 1 - CRPS(twin) / CRPS(baseline): positive means the twin is better.

| Ticker | Industry | Built by | Build s | Signals | Quarters | KPI | MAE twin | MAE naive | MAE seasonal | Skill vs naive | Skill vs seasonal | 80% coverage |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CMG | restaurant | hand | - | 9 | 30 | transactions | 4.05 | 2.55 | 7.10 | -0.14 | +0.63 | 0.61 |
| CMG | restaurant | hand | - | 9 | 30 | check | 1.20 | 0.77 | 1.07 | -0.07 | +0.48 | 0.62 |
| CMG | restaurant | hand | - | 9 | 30 | comps | 3.82 | 3.69 | 9.21 | -0.04 | +0.57 | 0.93 |
| CMG | restaurant | hand | - | 9 | 30 | rlom | 1.77 | 1.65 | 2.14 | -0.07 | +0.24 | 1.00 |
| CMG | restaurant | hand | - | 9 | 30 | revenue_growth | 3.86 | 3.92 | 9.48 | -0.06 | +0.56 | 0.97 |
| DAL | airline | hand | - | 6 | 26 | revenue_growth | 3.60 | 4.15 | 15.77 | +0.12 | +0.80 | 0.85 |
| DAL | airline | hand | - | 6 | 26 | op_margin | 2.40 | 5.03 | 2.76 | +0.37 | +0.01 | 1.00 |
| AAL | airlines | factory | - | 6 | 26 | revenue_growth | 3.79 | 3.80 | 14.60 | +0.11 | +0.75 | 0.96 |
| AAL | airlines | factory | - | 6 | 26 | op_margin | 2.60 | 5.68 | 4.18 | +0.49 | +0.36 | 0.85 |
| DHI | homebuilders | factory | - | 7 | 30 | revenue_growth | 4.88 | 5.07 | 9.35 | +0.13 | +0.52 | 0.90 |
| DRI | restaurants | factory | - | 6 | 30 | revenue_growth | 5.32 | 3.96 | 12.52 | -0.03 | +0.63 | 0.90 |
| DRI | restaurants | factory | - | 6 | 30 | op_margin | 2.14 | 1.96 | 0.91 | +0.11 | +0.03 | 0.97 |
| HLT | hotels | factory | - | 5 | 26 | revenue_growth | 4.72 | 4.55 | 14.30 | -0.05 | +0.67 | 0.88 |
| HLT | hotels | factory | - | 5 | 26 | op_margin | 2.11 | 3.06 | 1.71 | +0.30 | -0.11 | 0.96 |
| LEN | homebuilders | factory | - | 7 | 30 | revenue_growth | 9.34 | 9.50 | 20.09 | -0.04 | +0.50 | 0.83 |
| LEN | homebuilders | factory | - | 7 | 30 | op_margin | 3.37 | 3.75 | 4.17 | +0.16 | +0.17 | 0.69 |
| LUV | airlines | factory | - | 6 | 26 | revenue_growth | 3.20 | 3.37 | 12.82 | +0.07 | +0.78 | 0.85 |
| LUV | airlines | factory | - | 6 | 26 | op_margin | 4.10 | 4.70 | 2.75 | +0.09 | -0.41 | 0.73 |
| MAR | hotels | factory | - | 5 | 26 | revenue_growth | 4.73 | 4.11 | 19.96 | -0.07 | +0.72 | 0.92 |
| MAR | hotels | factory | - | 5 | 26 | op_margin | 2.34 | 2.72 | 1.75 | +0.20 | +0.23 | 0.77 |
| MCD | restaurants | factory | - | 6 | 30 | revenue_growth | 4.04 | 3.80 | 9.80 | -0.02 | +0.59 | 0.90 |
| MCD | restaurants | factory | - | 6 | 30 | op_margin | 8.93 | 7.08 | 12.06 | -0.20 | +0.31 | 0.90 |
| PHM | homebuilders | factory | - | 7 | 27 | revenue_growth | 4.74 | 4.45 | 11.94 | +0.33 | +0.61 | 0.96 |
| SBUX | restaurants | factory | - | 6 | 29 | revenue_growth | 6.37 | 5.03 | 10.71 | +0.05 | +0.42 | 0.81 |
| SBUX | restaurants | factory | - | 6 | 29 | op_margin | 1.99 | 2.43 | 3.27 | +0.63 | +0.64 | 0.86 |
| TGT | general_retail | factory | - | 5 | 31 | revenue_growth | 2.90 | 3.08 | 6.11 | +0.01 | +0.47 | 0.77 |
| TGT | general_retail | factory | - | 5 | 31 | op_margin | 1.12 | 1.27 | 1.68 | -0.05 | +0.26 | 0.90 |
| TXRH | restaurants | factory | - | 6 | 29 | revenue_growth | 3.97 | 4.15 | 7.74 | +0.21 | +0.57 | 0.93 |
| TXRH | restaurants | factory | - | 6 | 29 | op_margin | 1.26 | 1.52 | 1.25 | +0.08 | +0.03 | 0.93 |
| UAL | airlines | factory | - | 6 | 26 | revenue_growth | 3.78 | 4.13 | 17.22 | +0.45 | +0.81 | 0.81 |
| UAL | airlines | factory | - | 6 | 26 | op_margin | 2.20 | 4.57 | 2.99 | +0.52 | +0.27 | 1.00 |
| WMT | general_retail | factory | - | 5 | 31 | revenue_growth | 1.23 | 1.21 | 2.62 | -0.02 | +0.49 | 0.84 |
| WMT | general_retail | factory | - | 5 | 31 | op_margin | 0.43 | 0.58 | 0.52 | +0.16 | +0.16 | 0.87 |

Twin beats naive (CRPS) on 20 of 33 KPI series.
