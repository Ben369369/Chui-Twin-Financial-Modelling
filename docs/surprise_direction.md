# Surprise direction: does the twin call beat or miss?

Generated 2026-10-19 22:05 UTC by `scripts/reports/surprise_direction.py`. Walk-forward from 2017Q1 with the scorecard's exclusions; each forecast uses only data public an hour before the release, and each expectation only if it was public before that moment. A call is the sign of (twin median - expectation); the outcome is the sign of (actual - expectation). The best constant rule is "always beat" or "always miss", whichever scored more: a twin with no information scores about that. p is the one-sided binomial chance of at least that many hits by coin flip.

| Twin | KPI | Against | Quarters | Twin hits | Hit rate | Actual beat | Best constant rule | p (vs coin) |
|---|---|---|---|---|---|---|---|---|
| CMG | comps | consensus | 6 (2025Q1–2026Q2) | 3 | 50% | 3 | 50% | 0.66 |
| CMG | comps | guidance | 18 (2022Q1–2026Q2) | 13 | 72% | 13 | 72% | 0.05 |
| DAL | revenue_growth | guidance | 14 (2023Q2–2026Q3) | 9 | 64% | 7 | 50% | 0.21 |

Read a row as evidence of an information edge only if the hit rate clears the best constant rule, not just 50%, and p is small. With 6–18 quarters per row, none of these is conclusive.
