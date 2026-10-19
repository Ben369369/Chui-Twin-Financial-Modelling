# Surprise direction: does the twin call beat or miss?

Generated 2026-10-19 22:52 UTC by `scripts/reports/surprise_direction.py`. Walk-forward from 2017Q1 with the scorecard's exclusions; each forecast uses only data public an hour before the release, and each expectation only if it was public before that moment. A call is the sign of (twin median - expectation); the outcome is the sign of (actual - expectation). The best constant rule is "always beat" or "always miss", whichever scored more: a twin with no information scores about that. p is the one-sided binomial chance of at least that many hits by coin flip.

| Twin | KPI | Against | Quarters | Twin hits | Hit rate | Actual beat | Best constant rule | p (vs coin) |
|---|---|---|---|---|---|---|---|---|
| CMG | comps | consensus | 6 (2025Q1–2026Q2) | 3 | 50% | 3 | 50% | 0.66 |
| CMG | comps | guidance | 18 (2022Q1–2026Q2) | 13 | 72% | 13 | 72% | 0.05 |
| DAL | revenue_growth | guidance | 14 (2023Q2–2026Q3) | 9 | 64% | 7 | 50% | 0.21 |

Read a row as evidence of an information edge only if the hit rate clears the best constant rule, not just 50%, and p is small. With 6–18 quarters per row, none of these is conclusive.

## Accuracy: is the twin closer to the actual than the expectation?

Same quarters. Gain = CRPS(expectation) - CRPS(twin) per quarter; a point forecast's CRPS is its absolute error. Sign test: how often the twin was closer. Permutation p: exact one-sided paired test on the mean gain (all 2^n sign flips). This uses the size of each quarter's gain, so it has more power than beat/miss, but it answers a different question: closer than the expectation, not the direction of the surprise.

| Twin | KPI | Against | Quarters | Twin closer | Sign test p | Mean CRPS gain | Permutation p |
|---|---|---|---|---|---|---|---|
| CMG | comps | consensus | 6 | 2 of 6 | 0.891 | -0.37 | 0.812 |
| CMG | comps | guidance | 18 | 15 of 18 | 0.004 | +0.94 | 0.021 |
| DAL | revenue_growth | guidance | 14 | 11 of 14 | 0.029 | +1.06 | 0.005 |

Caveats: a company that guides low (Chipotle beat its guide in most quarters) can be beaten partly by correcting that bias; several tests on 6–18 quarters; the hand-built twins' structure was chosen on this backtest. None of this is a test against what the price already reflects.
