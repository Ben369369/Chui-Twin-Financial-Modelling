// Thin client over the FastAPI app (api/main.py). Every value the UI shows comes from here.

export type Quantiles = { p10: number; p50: number; p90: number; mean: number; sd: number }
export type KpiForecast = Record<string, Record<string, Quantiles>> // kpi -> period -> quantiles

export type Contribution = {
  kpi: string
  period: string
  driver: string
  signal: string | null
  value: number
  source_refs: string[]
}

export type Gap = {
  kpi: string
  period: string
  source: string
  expectation: number
  gap_mean: number
  prob_above: number
  source_ref: string
}

export type ForecastRecord = {
  ticker: string
  spec_hash: string
  as_of: string
  n_paths: number
  forecast: KpiForecast
  waterfall: Record<string, Record<string, Contribution[]>> // period -> kpi -> rows
  expectation_gaps: Gap[]
  scenario?: { shocks: string[]; forecast: KpiForecast; delta_mean: Record<string, Record<string, number>> }
}

export type TwinSummary = {
  ticker: string
  name: string
  template: string
  built_by: 'hand' | 'factory'
  kpis: string[]
  signals: string[]
}

export type TwinDetail = {
  ticker: string
  name: string
  built_by: string
  spec_hash: string
  as_of: string
  states_period: string
  states: Record<string, { mean: number; variance: number; contributions: Record<string, number> }>
  kpi_models: Record<string, { target: string; parents: string[]; lags: number[]; n_obs: number; sigma: number }>
  signals: { series: string; primitive: string; confidence: number }[]
}

export type History = {
  ticker: string
  reported: Record<string, Record<string, { value: number; source_ref: string }>>
  states: Record<string, Record<string, number>>
}

export type KpiScore = {
  n: number
  mae_twin: number
  mae_naive: number | null
  mae_seasonal: number | null
  skill_naive: number | null
  skill_seasonal: number | null
  coverage80: number | null
}

export type Scorecard = {
  generated: string
  test_from: string
  twins: {
    ticker: string
    industry: string
    built_by: string
    signals: number
    score: { gt_quarters: number; test_quarters: number; kpis: Record<string, KpiScore> }
  }[]
}

export type Shock = { primitive: string; period: string; size: number; halfLife: number }

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`/api${path}`)
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`)
  return r.json() as Promise<T>
}

export const api = {
  twins: () => get<TwinSummary[]>('/twins'),
  twin: (t: string) => get<TwinDetail>(`/twins/${t}`),
  history: (t: string) => get<History>(`/twins/${t}/history`),
  scorecard: () => get<Scorecard>('/scorecard'),
  forecast: (t: string, shocks: Shock[] = [], paths = 5000) => {
    const q = new URLSearchParams({ paths: String(paths) })
    for (const s of shocks) q.append('shock', `${s.primitive}:${s.period}:${s.size}:${s.halfLife}`)
    return get<ForecastRecord>(`/twins/${t}/forecast?${q}`)
  },
}

export const fmt = (v: number | null | undefined, d = 1) => (v == null ? '–' : v.toFixed(d))
export const signed = (v: number | null | undefined, d = 2) => (v == null ? '–' : `${v > 0 ? '+' : ''}${v.toFixed(d)}`)
export const label = (k: string) => k.replace(/_/g, ' ')

export type SharedSeries = { series: string; label: string; twins: { ticker: string; primitive: string; sign: number }[] }

export type PortfolioShock = {
  series: string
  label: string
  move: number | null
  size: number | null
  half_life: number
  twins: {
    ticker: string
    name: string
    primitive: string
    state_shock_sd: number
    series_sd: number
    series_move: number
    one_sd: number
    transform: string
    period: string
    impact: Record<string, Record<string, number>>
    base: Record<string, Record<string, number>>
  }[]
}

export const portfolioApi = {
  series: () => get<SharedSeries[]>('/portfolio/series'),
  shock: (series: string, move: number, halfLife = 2) =>
    get<PortfolioShock>(`/portfolio/shock?${new URLSearchParams({ series, move: String(move), half_life: String(halfLife) })}`),
}

// Display names from adapters/series_catalog.yaml, loaded once.
let labels: Record<string, string> = {}
export const loadSeriesLabels = () =>
  get<Record<string, string>>('/series/labels').then((l) => { labels = l }).catch(() => { /* fall back to raw ids */ })
export const seriesLabel = (s: string) => labels[s]
