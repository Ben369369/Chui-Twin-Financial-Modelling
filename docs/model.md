# Model (v0)

Everything here is generic. Names such as "primitive A" come from a template, and signal and KPI names come from a spec.

## 1. Signals → features (`engine/estimation/weighted.py`)

For signal *s* and period *p*, evaluated at `as_of`:

1. Keep only observations with `available_at ≤ as_of`. The effective date is `observed_at + lag_days`.
2. The anchor is *a = min(end of p, as_of date)*. The current, partial period is read at `as_of`.
3. level(a) = Σ wᵢ vᵢ / Σ wᵢ over observations with effective date in [a − 4·h, a], where wᵢ = 0.5^((a − dᵢ)/h) and *h* = `half_life_days`.
4. feature = transform(level(a), level(a − 364d)):
   - `yoy_log` = log ratio
   - `yoy_diff` = difference
   - `level` = level(a)
5. z = (feature − mean) / sd over all periods with a feature at `as_of` (at least 6 are required).

## 2. Features → states

Each primitive has a N(0, 1) prior. Each signal is a noisy reading of sign·state:

- precision pₛ = c/(1 − c) · 0.5^(staleness/h), where *c* = `confidence` and staleness = days since the newest observation used
- state mean = Σ pₛ · signₛ · zₛ / (1 + Σ pₛ)
- state variance = 1 / (1 + Σ pₛ)

Each signal's contribution pₛ·signₛ·zₛ/(1 + Σ p) is stored, so contributions sum exactly to the state mean. A primitive with no signals stays at its prior, N(0, 1).

## 3. States → KPIs (`engine/estimation/calibration.py`)

For each modeled KPI *k* with parent primitives *j*:

  y_t = a + Σ_j b_j · x_{j,t} [+ φ · y_{t−1}] + ε,  ε ~ N(0, σ²)

- Priors: b_j ~ N(prior_mean · sd_y, (prior_sd · sd_y)²). Edge priors are standardized: "one sd in the parent moves the child by `prior_mean` of its sd". φ takes the `lag` prior as given. The intercept is loose (2 · sd_y).
- The posterior is conjugate Gaussian given σ. σ² is iterated as (SSR + 2·sd_y²)/(n + 2).
- Only ground truth with `available_at ≤ as_of` is used. Periods listed in `exclude_from_calibration` are skipped.
- If y_{t−1} is missing but that period was reported (the company did not disclose this KPI), it is imputed with the historical mean.

Two optional structures, chosen per KPI in the spec:

- **`seasonal_lag`** adds y_{t−s}, where s is one year of periods. It suits seasonal levels such as quarterly airline margins.
- **`target: change`** models Δy_t = a + Σ_j b_j·Δx_{j,t} + ε and forecasts y_t = y_{t−1} + Δy_t. It suits year-over-year KPIs, where the news since the last report is in how the signals moved since then. The drift *a* has a tight prior (0.1·sd of Δy) because a rate cannot drift forever. Where both periods have estimates, the simulation differences the estimated state means, matching calibration, so state noise is not counted twice.

How each structure was chosen (2026-10-01): for CMG, level + lag lost to naive on every KPI, and change mode brought comps and revenue growth to parity on MAE. For DAL revenue growth, lag beat change mode (+0.12 vs +0.03 CRPS skill), so DAL keeps the lag. **These choices were made on the same backtest that is reported, which is mild selection bias.** The sealed Q3 forecast (resolves Oct 28) and twins built by the factory, which use the pack defaults with no tuning, are the clean tests.

Formula KPIs (e.g. `a + b`) are derived and never calibrated.

## 4. Simulation (`engine/simulation/montecarlo.py`)

Per path (vectorized over paths):

- Start states ~ N(mean, variance) at the latest estimated period.
- Each step forward: x ← ρ·x + innovation. Innovation = √(1 − ρ²)·N(0, 1) + Σ b_e · parent innovation, where b_e ~ edge prior (drawn once per path). ρ = `persistence`.
- Shock (primitive, period, size in sd, half-life): adds size·0.5^(k/hl) to the primitive, propagated to its children through the same sampled b_e.
- KPI coefficients ~ MVN(posterior) per path. y = coefs·[1, x, y_{t−1}] + σ·N(0, 1). The lag uses the reported value when known at `as_of`; otherwise it uses the path's own simulated value.

Outputs are p10, p50 and p90, the mean and sd, and the expectation gap: E[X] − X_ext and P(X > X_ext) for any guidance or consensus value available at `as_of`.

## 5. Attribution (`engine/attribution/`)

- **Waterfall:** E[y] = a + Σ b_j·ρ_j^k·Σ_s contribution_s + shock terms + φ·y_{t−1}. Each row keeps the source refs of the observations behind it. Formula KPIs are linearized at the component means.
- **Leave-one-signal-out:** everything is refit without signal *s* (states and calibration), and Δ = Y_all − Y_without_s is reported. Common random numbers keep it low-noise.

## 6. Evaluation (`engine/evaluation/`)

- Walk-forward: for each reported period, `as_of` = first release of that period − 1 hour, and everything is refit from scratch.
- Baselines:
  - `naive_last`: last reported value
  - `seasonal_naive`: the value one year earlier
  - external rows (e.g. `guidance`)
  - Built-in baseline spreads are the RMS of their own past errors, skipping excluded periods, so they get a fair CRPS.
- Metrics: MAE, RMSE, bias, CRPS (samples, exact), 80% interval coverage, and CRPS skill = 1 − CRPS_twin/CRPS_baseline on paired periods.

## Known weaknesses (v0)

- There are no seasonal terms. Seasonal KPIs (airline margins) lose to `seasonal_naive`.
- Errors in state estimates are ignored in calibration (errors-in-variables). Simulation adds state uncertainty on top of σ, so intervals are slightly wide.
- Standardization uses all history available at `as_of`, so z-scores of old periods shift a little as history grows.
- Primitive-to-primitive edges come only from priors. They shape scenarios and propagation, not the fitted point forecast.
