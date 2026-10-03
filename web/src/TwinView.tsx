import { useEffect, useState } from 'react'
import { api, fmt, label, shockLibrary, signed, type MeasuredShock, type ForecastRecord, type History, type Shock, type TwinDetail, type TwinSummary } from './api'
import { CountUp, Reveal } from './brand'
import { listen, take } from './bus'
import { DriversChart, ForecastChart, StatesChart } from './Charts'

// One-click scenarios. Shown only when the twin has the state; sizes are in sd of that state.
const PRESETS: { name: string; note: string; shocks: Record<string, number>; halfLife: number }[] = [
  { name: 'Food-safety scare', note: 'sentiment -2.5 sd, fades over 2 quarters', shocks: { sentiment: -2.5 }, halfLife: 2 },
  { name: 'Fuel / commodity spike', note: 'input cost +2 sd', shocks: { input_cost: 2 }, halfLife: 2 },
  { name: 'Price increase', note: 'price +1.5 sd, sticky', shocks: { price: 1.5 }, halfLife: 4 },
  { name: 'Demand slump', note: 'demand -2 sd', shocks: { demand: -2 }, halfLife: 1 },
  { name: 'Wage pressure', note: 'labor +2 sd, sticky', shocks: { labor: 2 }, halfLife: 4 },
]

function Scenario({ primitives, periods, busy, onRun, onClear }: {
  primitives: string[]
  periods: string[]
  busy: boolean
  onRun: (s: Shock[]) => void
  onClear: () => void
}) {
  const [sizes, setSizes] = useState<Record<string, number>>({})
  const [period, setPeriod] = useState(periods[0] ?? '')
  const [halfLife, setHalfLife] = useState(1)
  useEffect(() => { setPeriod(periods[0] ?? '') }, [periods])
  const shocks = Object.entries(sizes).filter(([, v]) => v !== 0)
    .map(([primitive, size]) => ({ primitive, period, size, halfLife }))
  const [measured, setMeasured] = useState<MeasuredShock[]>([])
  useEffect(() => { shockLibrary().then(setMeasured) }, [])
  // Presets take their decay speed from the measured shock library when one matches.
  const presets = PRESETS.filter((p) => Object.keys(p.shocks).every((k) => primitives.includes(k))).map((p) => {
    const m = measured.find((x) => x.preset === p.name)
    return m ? { ...p, halfLife: Math.round(m.half_life_quarters * 2) / 2,
                 note: `${p.note.split(',')[0]}; fades like ${m.ticker} ${m.event} (half-life ${m.half_life_quarters} quarters, measured)` } : p
  })
  const measuredUsed = measured.filter((m) => presets.some((p) => p.name === m.preset))
  const [active, setActive] = useState<string | null>(null)
  const applyPreset = (p: (typeof PRESETS)[number]) => {
    setSizes(p.shocks); setHalfLife(p.halfLife); setActive(p.name)
    onRun(Object.entries(p.shocks).map(([primitive, size]) => ({ primitive, period, size, halfLife: p.halfLife })))
  }

  return (
    <section className="card p-4">
      <h3 className="serif brand-heading text-lg font-semibold">Scenario</h3>
      <p className="mb-3 text-xs muted">
        Shock a hidden state by a number of standard deviations. The shock flows through the causal graph to every KPI.
        A food-safety scare is roughly sentiment −2 to −3.
      </p>
      <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Preset scenarios">
        {presets.map((p) => (
          <button key={p.name} className="chip" aria-pressed={active === p.name} title={p.note} disabled={busy}
                  onClick={() => applyPreset(p)}>{p.name}</button>
        ))}
      </div>
      {measuredUsed.length > 0 && (
        <p className="-mt-2 mb-3 text-xs muted">
          Measured decay: {measuredUsed.map((m) => `${m.name} (${m.ticker} ${m.event}): trough ${signed(m.trough_deviation_pct, 1)}%, `
            + `half-life ${m.half_life_quarters} quarters`).join(' · ')}. From reported revenue and comps; see shocks/library.yaml.
        </p>
      )}
      <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {primitives.map((p) => (
          <label key={p} className="flex items-center gap-3 text-sm">
            <span className="w-24 secondary">{label(p)}</span>
            <input type="range" min={-3} max={3} step={0.5} value={sizes[p] ?? 0} className="flex-1"
                   aria-label={`${label(p)} shock in standard deviations`}
                   onChange={(e) => { setActive(null); setSizes({ ...sizes, [p]: Number(e.target.value) }) }} />
            <span className="w-10 text-right tnum">{signed(sizes[p] ?? 0, 1)}</span>
          </label>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
        <label className="secondary">Starts
          <select className="ml-2 rounded border px-2 py-1" style={{ borderColor: 'var(--border)', background: 'var(--surface-1)' }}
                  value={period} onChange={(e) => setPeriod(e.target.value)}>
            {periods.map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>
        <label className="secondary">Half-life
          <select className="ml-2 rounded border px-2 py-1" style={{ borderColor: 'var(--border)', background: 'var(--surface-1)' }}
                  value={halfLife} onChange={(e) => setHalfLife(Number(e.target.value))}>
            {[...new Set([0.5, 1, 2, 4, 8, halfLife])].sort((a, b) => a - b).map((h) => <option key={h} value={h}>{h} quarter{h === 1 ? '' : 's'}</option>)}
          </select>
        </label>
        <button className="primary" disabled={busy || shocks.length === 0} onClick={() => onRun(shocks)}>
          {busy ? 'Simulating…' : 'Run scenario'}
        </button>
        <button className="chip" onClick={() => { setSizes({}); setActive(null); onClear() }}>Reset</button>
      </div>
    </section>
  )
}

export function TwinView({ ticker, twins, onTicker }: { ticker: string; twins: TwinSummary[]; onTicker: (t: string) => void }) {
  const [detail, setDetail] = useState<TwinDetail | null>(null)
  const [history, setHistory] = useState<History | null>(null)
  const [fc, setFc] = useState<ForecastRecord | null>(null)
  const [scen, setScen] = useState<ForecastRecord | null>(null)
  const [kpi, setKpi] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    setErr(null); setScen(null)
    Promise.all([api.twin(ticker), api.history(ticker), api.forecast(ticker)])
      .then(([d, h, f]) => {
        if (!live) return
        setDetail(d); setHistory(h); setFc(f)
        setKpi((k) => (k && k in f.forecast ? k : Object.keys(f.forecast)[0]))
      })
      .catch((e) => live && setErr(String(e)))
    return () => { live = false }
  }, [ticker])

  const run = (shocks: Shock[]) => {
    setBusy(true)
    api.forecast(ticker, shocks).then(setScen).catch((e) => setErr(String(e))).finally(() => setBusy(false))
  }

  // Scenarios handed over by the chat assistant ("Show CMG with this scenario").
  useEffect(() => {
    if (!fc) return
    const apply = () => {
      const a = take('open_twin', ticker)
      if (a && a.shocks.length) run(a.shocks)
    }
    apply()
    return listen(apply)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker, fc])

  const summary = twins.find((t) => t.ticker === ticker)
  const periods = fc ? Object.keys(fc.forecast[kpi] ?? {}).sort() : []
  const first = periods[0]
  const gaps = fc?.expectation_gaps.filter((g) => g.kpi === kpi) ?? []

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Twin">
        {twins.map((t) => (
          <button key={t.ticker} className="chip" aria-pressed={t.ticker === ticker} onClick={() => onTicker(t.ticker)}>
            {t.ticker}
          </button>
        ))}
      </div>

      {err && <p className="text-sm" style={{ color: 'var(--bad-text)' }}>{err}</p>}
      {!fc || !detail || !history ? <p className="muted">Loading {ticker}…</p> : (
        <div style={{ opacity: busy ? 0.6 : 1 }}>
          <div className="reveal mb-4">
            <h2 className="serif brand-heading text-2xl font-semibold">{summary?.name ?? ticker}</h2>
            <p className="text-xs muted">
              {detail.built_by === 'factory' ? 'Built by the twin factory from the ticker' : 'Hand-built spec'} ·
              {' '}{detail.signals.length} signals · as of {fc.as_of.slice(0, 16).replace('T', ' ')} UTC ·
              {' '}{fc.n_paths.toLocaleString()} paths · spec {fc.spec_hash.slice(0, 12)}
            </p>
          </div>

          <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="KPI">
            {Object.keys(fc.forecast).map((k) => (
              <button key={k} className="chip" aria-pressed={k === kpi} onClick={() => setKpi(k)}>{label(k)}</button>
            ))}
          </div>

          <div className="space-y-4">
            <Reveal i={1}><ForecastChart key={`${kpi}-${scen?.scenario?.shocks.join() ?? 'base'}`} kpi={kpi} reported={history.reported[kpi] ?? {}} forecast={fc.forecast[kpi]}
                           scenario={scen?.scenario?.forecast[kpi]}
                           guidance={Object.fromEntries(gaps.filter((g) => g.source === 'guidance').map((g) => [g.period, g.expectation]))} /></Reveal>

            {gaps.length > 0 && (
              <section className="card reveal p-4 text-sm">
                <h3 className="serif brand-heading mb-1 text-lg font-semibold">Versus expectations</h3>
                {gaps.map((g) => (
                  <p key={g.period + g.source} className="secondary">
                    {g.period}: {g.source} {fmt(g.expectation, 1)} · twin mean {signed(g.gap_mean, 1)} from it ·
                    {' '}P(outcome above {g.source}) <b style={{ color: 'var(--text-primary)' }}>{Math.round(g.prob_above * 100)}%</b>
                  </p>
                ))}
              </section>
            )}

            {scen?.scenario && (
              <section key={scen.scenario.shocks.join()} className="card fade-in p-4 text-sm" aria-live="polite">
                <h3 className="serif brand-heading mb-1 text-lg font-semibold">Scenario impact on the mean</h3>
                <p className="mb-2 text-xs muted">{scen.scenario.shocks.join(', ')}</p>
                <div className="flex flex-wrap gap-x-6 gap-y-1">
                  {Object.entries(scen.scenario.delta_mean).map(([k, byP]) => (
                    <span key={k} className="secondary">{label(k)}:{' '}
                      {Object.entries(byP).sort().map(([p, v]) => (
                        <span key={p} className="tnum"> {p} <b style={{ color: 'var(--text-primary)' }}>{v > 0 ? '+' : v < 0 ? '−' : ''}<CountUp value={Math.abs(v)} decimals={1} duration={700} /></b></span>
                      ))}
                    </span>
                  ))}
                </div>
              </section>
            )}

            <Reveal i={2} className="grid gap-4 lg:grid-cols-2">
              {first && <DriversChart kpi={kpi} period={first} rows={(scen ?? fc).waterfall[first]?.[kpi] ?? []} />}
              <StatesChart period={`${detail.states_period} (latest estimate)`} states={detail.states} />
            </Reveal>

            <Reveal i={3}><Scenario primitives={Object.keys(detail.states)} periods={periods} busy={busy} onRun={run}
                      onClear={() => setScen(null)} /></Reveal>
          </div>
        </div>
      )}
    </div>
  )
}
