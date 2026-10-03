import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmt, label, portfolioApi, signed, type PortfolioShock, type SharedSeries } from './api'
import { listen, take } from './bus'

// Presets in natural units: what people actually say ("fuel up 30%").
const PRESETS: { name: string; series: string; move: number }[] = [
  { name: 'Jet fuel +30%', series: 'fred:DJFUELUSGULF', move: 30 },
  { name: 'Restaurant sales −5%', series: 'fred:RSFSDP', move: -5 },
  { name: 'Air travel −10%', series: 'tsa:checkpoint_throughput', move: -10 },
  { name: 'Beef prices +20%', series: 'fred:APU0000703112', move: 20 },
  { name: 'Restaurant wages +6%', series: 'bls:CES7072200003', move: 6 },
]

type Bar = { name: string; ticker: string; kpi: string; value: number; base: number; how: string }

export function EconomyShock({ onOpen }: { onOpen: (t: string) => void }) {
  const [series, setSeries] = useState<SharedSeries[]>([])
  const [pick, setPick] = useState('fred:DJFUELUSGULF')
  const [move, setMove] = useState(30)
  const [res, setRes] = useState<PortfolioShock | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [asTable, setAsTable] = useState(false)

  const run = (s = pick, m = move) => {
    setBusy(true); setErr(null)
    portfolioApi.shock(s, m).then(setRes).catch((e) => setErr(String(e))).finally(() => setBusy(false))
  }

  useEffect(() => {
    portfolioApi.series().then((s) => {
      const shared = s.filter((x) => x.twins.length >= 2)
      setSeries(shared)
      // Open with a live result: a shock handed over by the chat, else the first runnable preset.
      const handed = take('economy_shock')
      const first = handed ? { series: handed.series, move: handed.move }
        : PRESETS.find((p) => shared.some((x) => x.series === p.series))
      if (first) { setPick(first.series); setMove(first.move); run(first.series, first.move) }
    }).catch((e) => setErr(String(e)))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => listen(() => {
    const a = take('economy_shock')
    if (a) { setPick(a.series); setMove(a.move); run(a.series, a.move) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [])

  const bars: Bar[] = (res?.twins ?? []).flatMap((t) =>
    Object.entries(t.impact).map(([kpi, byP]) => ({
      name: `${t.ticker} · ${label(kpi)}`, ticker: t.ticker, kpi,
      value: byP[t.period], base: t.base[kpi][t.period],
      how: `${label(t.primitive)} ${signed(t.state_shock_sd)} sd in ${t.period}`,
    }))).filter((b) => Math.abs(b.value) > 0.005).sort((a, b) => a.value - b.value)
  const yoy = res?.twins[0]?.transform === 'yoy_log'

  return (
    <section className="card p-4">
      <div className="mb-1 flex items-start justify-between gap-4">
        <div>
          <h3 className="serif brand-heading text-lg font-semibold">Economy shock</h3>
          <p className="text-xs muted">
            Move one shared data series and watch every twin that uses it respond, each through its own calibrated
            causal graph. Impact is the change in next quarter's expected KPI, in points.
          </p>
        </div>
        {res && <button className="chip shrink-0" aria-pressed={asTable} onClick={() => setAsTable(!asTable)}>{asTable ? 'Chart' : 'Table'}</button>}
      </div>

      <div className="my-3 flex flex-wrap gap-2" role="group" aria-label="Economy shock presets">
        {PRESETS.filter((p) => series.some((s) => s.series === p.series)).map((p) => (
          <button key={p.name} className="chip" disabled={busy} aria-pressed={res?.series === p.series && res?.move === p.move}
                  onClick={() => { setPick(p.series); setMove(p.move); run(p.series, p.move) }}>{p.name}</button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="secondary">Series
          <select className="ml-2 max-w-72 rounded border px-2 py-1" style={{ borderColor: 'var(--border)', background: 'var(--surface-1)' }}
                  value={pick} onChange={(e) => setPick(e.target.value)}>
            {series.map((s) => <option key={s.series} value={s.series}>{s.label} · {s.twins.length} twins</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 secondary">Move
          <input type="range" min={-50} max={50} step={1} value={move} onChange={(e) => setMove(Number(e.target.value))}
                 aria-label="Series move, percent year over year" />
          <span className="w-14 text-right tnum" style={{ color: 'var(--text-primary)' }}>{signed(move, 0)}%</span>
        </label>
        <button className="primary" disabled={busy || move === 0} onClick={() => run()}>{busy ? 'Simulating…' : 'Run shock'}</button>
      </div>
      {err && <p className="mt-2 text-sm" style={{ color: 'var(--bad-text)' }}>{err}</p>}

      {res && (
        <div key={`${res.series}${res.move}`} className="fade-in mt-4" style={{ opacity: busy ? 0.6 : 1 }}>
          <p className="mb-2 text-xs secondary">
            {res.label} {signed(res.move, 0)}{yoy ? '% year over year' : ''}
            {res.twins[0] && <> = {signed(res.twins[0].series_sd)} sd of its own history (1 sd ≈ {fmt(res.twins[0].one_sd, 1)}{yoy ? '%' : ''}).</>}
            {' '}{res.twins.length} twins exposed. Click a bar to open that twin.
          </p>
          {asTable ? (
            <table className="data w-full">
              <thead><tr><th>Twin · KPI</th><th>Expected before</th><th>Impact</th><th>Applied as</th></tr></thead>
              <tbody>{bars.map((b) => (
                <tr key={b.name} className="clickable" onClick={() => onOpen(b.ticker)}>
                  <td>{b.name}</td><td>{fmt(b.base, 2)}</td><td>{signed(b.value)}</td><td className="muted">{b.how}</td>
                </tr>))}</tbody>
            </table>
          ) : (
            <div className="chart-wipe">
              <ResponsiveContainer width="100%" height={Math.max(140, bars.length * 26 + 30)}>
                <BarChart data={bars} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 8 }} barCategoryGap={3}>
                  <CartesianGrid stroke="var(--grid)" horizontal={false} />
                  <XAxis type="number" stroke="var(--axis)" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} tickLine={false}
                         tickFormatter={(v: number) => v.toFixed(1)} />
                  <YAxis type="category" dataKey="name" stroke="var(--axis)" width={190} tickLine={false}
                         tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                  <ReferenceLine x={0} stroke="var(--axis)" />
                  <Tooltip cursor={{ fill: 'var(--wash)' }} content={({ active, payload }) => {
                    if (!active || !payload?.length) return null
                    const b = payload[0].payload as Bar
                    return <div className="card px-3 py-2 text-xs"><div className="font-semibold">{b.name}</div>
                      <div>{signed(b.value)} pts (from {fmt(b.base, 2)})</div><div className="muted">Applied as {b.how}</div></div>
                  }} />
                  <Bar dataKey="value" radius={4} isAnimationActive={false} cursor="pointer"
                       onClick={(d) => onOpen((d as unknown as Bar).ticker)}>
                    {bars.map((b) => <Cell key={b.name} fill={b.value >= 0 ? 'var(--pos)' : 'var(--neg)'} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
