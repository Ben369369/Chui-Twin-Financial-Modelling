import { useState, type ReactNode } from 'react'
import {
  Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { fmt, label, seriesLabel, signed, type Contribution, type Quantiles } from './api'

const axis = { stroke: 'var(--axis)', tick: { fill: 'var(--text-muted)', fontSize: 11 }, tickLine: false }
const grid = <CartesianGrid stroke="var(--grid)" vertical={false} />

function Panel({ title, sub, table, children }: { title: string; sub?: string; table: ReactNode; children: ReactNode }) {
  const [asTable, setAsTable] = useState(false)
  return (
    <section className="card p-4">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <h3 className="serif brand-heading text-lg font-semibold">{title}</h3>
          {sub && <p className="text-xs muted">{sub}</p>}
        </div>
        <button className="chip shrink-0" aria-pressed={asTable} onClick={() => setAsTable(!asTable)}>
          {asTable ? 'Chart' : 'Table'}
        </button>
      </div>
      {asTable ? <div className="fade-in overflow-x-auto">{table}</div> : <div className="chart-wipe">{children}</div>}
    </section>
  )
}

function TipBox({ children }: { children: ReactNode }) {
  return (
    <div className="card max-w-xs px-3 py-2 text-xs shadow-sm" style={{ background: 'var(--surface-1)' }}>
      {children}
    </div>
  )
}

export function prettySeries(s: string): string {
  const known = seriesLabel(s)
  if (known) return known
  const [src, ...rest] = s.split(':')
  const q = rest.join(':')
  const names: Record<string, string> = {
    fred: 'FRED', bls: 'BLS', tsa: 'TSA checkpoint travelers', wiki: 'Wikipedia views',
    sitemap: 'Sitemap count', gdelt: 'News',
  }
  if (src === 'gdelt') return `News ${q.startsWith('tone:') ? 'tone' : 'volume'}: ${q.split(':').slice(1).join(':')}`
  if (src === 'wiki') return `Wikipedia views: ${q.replace(/_/g, ' ')}`
  if (src === 'tsa') return names.tsa
  if (src === 'sitemap') return `Sitemap count: ${q.replace(/_/g, ' ')}`
  return `${names[src] ?? src} ${q}`
}

function prettyDriver(driver: string, kpi: string): string {
  if (driver === 'baseline') return 'Intercept'
  if (driver === `${kpi}[t-1]`) return 'Last reported'
  const m = driver.match(/\[(.*)\]$/)
  if (m && driver.startsWith(kpi)) return m[1].startsWith('t-') ? 'Same quarter last year' : `${label(m[1])[0].toUpperCase()}${label(m[1]).slice(1)}`
  return label(driver)
}

const shortRef = (r: string) => {
  const m = r.match(/SEC (\S+)/) ?? r.match(/accn:(\S+)/)
  return m ? `SEC filing ${m[1]}` : r.split(' | ')[0].slice(0, 80)
}

// ---------------------------------------------------------------- forecast

function shiftQuarter(p: string, n: number): string {
  const [y, q] = p.split('Q').map(Number)
  const i = y * 4 + (q - 1) + n
  return `${Math.floor(i / 4)}Q${(i % 4) + 1}`
}

function quarterSpan(a: string, b: string): string[] {
  const out: string[] = []
  for (let p = a; out.length < 200; p = shiftQuarter(p, 1)) { out.push(p); if (p === b) break }
  return out
}

type FRow = {
  period: string
  reported?: number
  ref?: string
  band?: [number, number]
  p50?: number
  sBand?: [number, number]
  sP50?: number
  guide?: number
}

export function ForecastChart(props: {
  kpi: string
  reported: Record<string, { value: number; source_ref: string }>
  forecast: Record<string, Quantiles>
  scenario?: Record<string, Quantiles>
  guidance?: Record<string, number>
}) {
  const { kpi, reported, forecast, scenario, guidance } = props
  const future = Object.keys(forecast).sort().filter((p) => !(p in reported))
  const reportedSorted = Object.keys(reported).sort()
  const last = reportedSorted[reportedSorted.length - 1]
  // Every quarter on the axis, so undisclosed quarters show as gaps instead of being squeezed out.
  const past = last ? quarterSpan(shiftQuarter(last, -11), last) : []
  const rows: FRow[] = past.map((p) => (p in reported
    ? { period: p, reported: reported[p].value, ref: reported[p].source_ref } : { period: p }))
  if (last) {
    // Join the forecast to the last reported point so the projection reads as a continuation.
    const anchor = rows[rows.length - 1]
    anchor.p50 = anchor.reported
    anchor.band = [anchor.reported!, anchor.reported!]
    if (scenario) { anchor.sP50 = anchor.reported; anchor.sBand = [anchor.reported!, anchor.reported!] }
  }
  for (const p of future) {
    const q = forecast[p]
    const s = scenario?.[p]
    rows.push({ period: p, band: [q.p10, q.p90], p50: q.p50, guide: guidance?.[p],
                ...(s ? { sBand: [s.p10, s.p90] as [number, number], sP50: s.p50 } : {}) })
  }

  const table = (
    <table className="data w-full">
      <thead><tr><th>Quarter</th><th>Reported</th><th>p10</th><th>Median</th><th>p90</th>
        {scenario && <><th>Scenario median</th><th>Scenario p10–p90</th></>}<th>Source</th></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.period}>
            <td>{r.period}</td><td>{fmt(r.reported, 1)}</td>
            <td>{r.reported == null ? fmt(r.band?.[0]) : ''}</td>
            <td>{r.reported == null ? fmt(r.p50) : ''}</td>
            <td>{r.reported == null ? fmt(r.band?.[1]) : ''}</td>
            {scenario && <><td>{r.reported == null ? fmt(r.sP50) : ''}</td>
              <td>{r.reported == null && r.sBand ? `${fmt(r.sBand[0])} – ${fmt(r.sBand[1])}` : ''}</td></>}
            <td className="muted">{r.ref ? shortRef(r.ref) : 'simulated'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )

  return (
    <Panel title={label(kpi)} sub="Reported quarters, then the simulated median and 80% band (p10–p90)" table={table}>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={rows} margin={{ top: 8, right: 24, bottom: 4, left: 0 }}>
          {grid}
          <XAxis dataKey="period" {...axis} interval="preserveStartEnd" minTickGap={18} />
          <YAxis {...axis} width={44} tickFormatter={(v: number) => v.toFixed(0)} />
          <ReferenceLine y={0} stroke="var(--axis)" />
          <Tooltip
            cursor={{ stroke: 'var(--axis)' }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const r = payload[0].payload as FRow
              return (
                <TipBox>
                  <div className="mb-1 font-semibold">{r.period}</div>
                  {r.reported != null ? (
                    <>
                      <div>Reported: <b>{fmt(r.reported, 1)}</b></div>
                      {r.ref && <div className="mt-1 muted break-words">{shortRef(r.ref)}</div>}
                    </>
                  ) : (
                    <>
                      <div>Median <b>{fmt(r.p50)}</b>, 80% band {fmt(r.band?.[0])} to {fmt(r.band?.[1])}</div>
                      {r.guide != null && <div>Guidance <b>{fmt(r.guide)}</b></div>}
                      {r.sP50 != null && <div>Scenario median <b>{fmt(r.sP50)}</b> ({signed((r.sP50 ?? 0) - (r.p50 ?? 0), 1)})</div>}
                    </>
                  )}
                </TipBox>
              )
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12, color: 'var(--text-secondary)' }} />
          <Area dataKey="band" name="80% band" fill="var(--series-1)" fillOpacity={0.14} stroke="none" isAnimationActive={false} />
          {scenario && <Area dataKey="sBand" name="Scenario 80% band" fill="var(--series-2)" fillOpacity={0.14} stroke="none" isAnimationActive={false} />}
          <Line dataKey="reported" name="Reported" stroke="var(--text-primary)" strokeWidth={2} dot={{ r: 4 }} connectNulls={false} isAnimationActive={false} />
          <Line dataKey="p50" name="Twin median" stroke="var(--series-1)" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 4 }} isAnimationActive={false} />
          {guidance && Object.keys(guidance).length > 0 && (
            <Line dataKey="guide" name="Guidance" stroke="var(--text-secondary)" strokeWidth={0} isAnimationActive={false} legendType="diamond"
                  dot={{ r: 6, fill: 'var(--text-secondary)', stroke: 'var(--surface-1)', strokeWidth: 2 }} />
          )}
          {scenario && <Line dataKey="sP50" name="Scenario median" stroke="var(--series-2)" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 4 }} isAnimationActive={false} />}
        </ComposedChart>
      </ResponsiveContainer>
    </Panel>
  )
}

// ---------------------------------------------------------------- drivers

type DRow = { name: string; value: number; refs: string[] }

export function DriversChart({ kpi, period, rows }: { kpi: string; period: string; rows: Contribution[] }) {
  const [picked, setPicked] = useState<DRow | null>(null)
  // Starting points (intercept, last reported value, guidance) are levels, not drivers; listed separately.
  const isStart = (c: Contribution) => c.driver === 'baseline' || c.driver.startsWith(`${kpi}[`)
  const startMap = new Map<string, Contribution>()
  for (const c of rows.filter(isStart)) {
    const cur = startMap.get(c.driver)
    startMap.set(c.driver, cur ? { ...cur, value: cur.value + c.value, source_refs: [...cur.source_refs, ...c.source_refs] } : c)
  }
  const start = [...startMap.values()]
  const agg = new Map<string, DRow>()
  for (const c of rows.filter((c) => !isStart(c))) {
    const name = c.signal ? (c.signal.startsWith('shock:') ? `Scenario: ${c.signal.slice(6)}` : prettySeries(c.signal)) : c.driver
    const key = `${c.driver}|${name}`
    const cur = agg.get(key) ?? { name: `${name}  (${label(c.driver)})`, value: 0, refs: [] }
    cur.value += c.value
    cur.refs = [...new Set([...cur.refs, ...c.source_refs])]
    agg.set(key, cur)
  }
  const data = [...agg.values()].filter((d) => Math.abs(d.value) > 0.005).sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
  const total = rows.reduce((s, c) => s + c.value, 0)

  const table = (
    <table className="data w-full">
      <thead><tr><th>Term</th><th>Contribution</th><th>Sources</th></tr></thead>
      <tbody>
        {[...start.map((c) => ({ name: prettyDriver(c.driver, kpi), value: c.value, refs: c.source_refs })), ...data].map((d) => (
          <tr key={d.name}><td>{d.name}</td><td>{signed(d.value)}</td><td className="muted">{d.refs.length}</td></tr>
        ))}
        <tr><td><b>Expected value</b></td><td><b>{fmt(total, 2)}</b></td><td /></tr>
      </tbody>
    </table>
  )

  return (
    <Panel title={`What moves ${label(kpi)}, ${period}`}
           sub="Each bar is one signal's contribution to the expected value, in KPI points. Click a bar for its sources."
           table={table}>
      <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        {start.map((c) => (
          <span key={c.driver} className="secondary">
            {prettyDriver(c.driver, kpi)}{c.signal?.startsWith('imputed') ? ' (not disclosed: historical mean)' : ''} <b className="tnum" style={{ color: 'var(--text-primary)' }}>{signed(c.value)}</b>
          </span>
        ))}
        <span className="secondary">Expected <b className="tnum" style={{ color: 'var(--text-primary)' }}>{fmt(total, 2)}</b></span>
      </div>
      {data.length === 0 ? <p className="text-sm muted">No signal moved this KPI this period.</p> : (
        <ResponsiveContainer width="100%" height={Math.max(120, data.length * 34 + 30)}>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 8 }} barCategoryGap={4}>
            <CartesianGrid stroke="var(--grid)" horizontal={false} />
            <XAxis type="number" {...axis} tickFormatter={(v: number) => v.toFixed(1)} />
            <YAxis type="category" dataKey="name" {...axis} width={250} />
            <ReferenceLine x={0} stroke="var(--axis)" />
            <Tooltip cursor={{ fill: 'var(--wash)' }} content={({ active, payload }) => active && payload?.length ? (
              <TipBox>
                <div className="font-semibold">{(payload[0].payload as DRow).name}</div>
                <div>{signed((payload[0].payload as DRow).value)} pts · {(payload[0].payload as DRow).refs.length} source(s)</div>
              </TipBox>) : null} />
            <Bar dataKey="value" radius={4} onClick={(d) => setPicked(d as unknown as DRow)} cursor="pointer" isAnimationActive={false}>
              {data.map((d) => <Cell key={d.name} fill={d.value >= 0 ? 'var(--pos)' : 'var(--neg)'} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
      {picked && (
        <div key={picked.name} className="fade-in mt-3 rounded-md p-3 text-xs" style={{ background: 'var(--wash)' }}>
          <div className="mb-1 font-semibold">{picked.name}: sources</div>
          <ul className="list-disc space-y-1 pl-4 break-all secondary">
            {picked.refs.slice(0, 6).map((r) => <li key={r}>{r}</li>)}
          </ul>
        </div>
      )}
    </Panel>
  )
}

// ---------------------------------------------------------------- states

export function StatesChart({ period, states }: {
  period: string
  states: Record<string, { mean: number; variance: number; contributions: Record<string, number> }>
}) {
  const data = Object.entries(states).map(([name, s]) => ({
    name: label(name), mean: s.mean, err: Math.sqrt(s.variance), n: Object.keys(s.contributions).length,
  }))
  const table = (
    <table className="data w-full">
      <thead><tr><th>State</th><th>Estimate (sd)</th><th>± 1 sd</th><th>Signals</th></tr></thead>
      <tbody>{data.map((d) => <tr key={d.name}><td>{d.name}</td><td>{signed(d.mean)}</td><td>{fmt(d.err, 2)}</td><td>{d.n}</td></tr>)}</tbody>
    </table>
  )
  return (
    <Panel title={`Hidden operating states, ${period}`}
           sub="Standard deviations from the company's own history; 0 = normal. Hover for the uncertainty (±1 sd)."
           table={table}>
      <ResponsiveContainer width="100%" height={data.length * 34 + 30}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 8 }} barCategoryGap={6}>
          <CartesianGrid stroke="var(--grid)" horizontal={false} />
          <XAxis type="number" domain={[-2.5, 2.5]} ticks={[-2, -1, 0, 1, 2]} {...axis} />
          <YAxis type="category" dataKey="name" {...axis} width={90} />
          <ReferenceLine x={0} stroke="var(--axis)" />
          <Tooltip cursor={{ fill: 'var(--wash)' }} content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0].payload as (typeof data)[number]
            return <TipBox><div className="font-semibold">{d.name}</div>
              <div>{signed(d.mean)} sd ± {fmt(d.err, 2)} · {d.n ? `${d.n} signal(s)` : 'no signal: prior only'}</div></TipBox>
          }} />
          <Bar dataKey="mean" radius={4} isAnimationActive={false}>
            {data.map((d) => <Cell key={d.name} fill={d.mean >= 0 ? 'var(--pos)' : 'var(--neg)'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </Panel>
  )
}
