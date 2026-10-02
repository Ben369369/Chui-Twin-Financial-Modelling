import { useMemo, useState } from 'react'
import { CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from 'recharts'
import { fmt, label, signed, type KpiScore, type Scorecard } from './api'
import { CountUp, Reveal } from './brand'

const INDUSTRY_NAMES: Record<string, string> = {
  restaurant: 'Restaurants', restaurants: 'Restaurants', airline: 'Airlines', airlines: 'Airlines',
  hotels: 'Hotels', homebuilders: 'Homebuilders', general_retail: 'General retail',
}

type Row = { ticker: string; ind: string; built_by: string; kpi: string; s: KpiScore }
type SortKey = 'ticker' | 'ind' | 'kpi' | 'mae_twin' | 'skill_naive' | 'skill_seasonal' | 'coverage80'

function Skill({ v }: { v: number | null }) {
  // Glyph + sign + value: color is never the only cue.
  if (v == null) return <span className="muted">–</span>
  const good = v > 0
  return <span style={{ color: good ? 'var(--good-text)' : 'var(--bad-text)' }}>{good ? '▲' : '▼'} {signed(v)}</span>
}

function Tile({ i, children, labelText, note }: { i: number; children: React.ReactNode; labelText: string; note?: string }) {
  return (
    <Reveal i={i}>
      <div className="card lift h-full p-4">
        <div className="text-3xl font-semibold">{children}</div>
        <div className="mt-1 text-sm secondary">{labelText}</div>
        {note && <div className="mt-1 text-xs muted">{note}</div>}
      </div>
    </Reveal>
  )
}

function SkillStrip({ rows, onOpen }: { rows: Row[]; onOpen: (t: string) => void }) {
  const industries = [...new Set(rows.map((r) => r.ind))].sort()
  // Numeric rows (one per industry) with a small deterministic jitter so overlapping series stay visible.
  const data = rows.filter((r) => r.s.skill_naive != null).map((r, i) => ({
    x: Math.max(-1, Math.min(1, r.s.skill_naive as number)), raw: r.s.skill_naive as number,
    y: industries.indexOf(r.ind) + ((i * 37) % 7 - 3) * 0.06,
    ind: r.ind, ticker: r.ticker, kpi: r.kpi, mae: r.s.mae_twin, maeN: r.s.mae_naive,
  }))
  return (
    <section className="card p-4">
      <h3 className="serif brand-heading text-lg font-semibold">Where the twin beats last quarter</h3>
      <p className="mb-2 text-xs muted">
        Each dot is one KPI series. Right of zero, the twin's probabilistic error (CRPS) is lower than "same as last quarter".
        Click a dot to open that twin.
      </p>
      <div className="chart-wipe"><ResponsiveContainer width="100%" height={industries.length * 46 + 50}>
        <ScatterChart margin={{ top: 8, right: 24, bottom: 18, left: 8 }}>
          <CartesianGrid stroke="var(--grid)" />
          <XAxis type="number" dataKey="x" domain={[-1, 1]} ticks={[-1, -0.5, 0, 0.5, 1]} stroke="var(--axis)"
                 tick={{ fill: 'var(--text-muted)', fontSize: 11 }} tickLine={false}
                 label={{ value: 'CRPS skill vs last quarter', position: 'insideBottom', offset: -10, fill: 'var(--text-muted)', fontSize: 11 }} />
          <YAxis type="number" dataKey="y" domain={[-0.6, industries.length - 0.4]} ticks={industries.map((_, i) => i)}
                 tickFormatter={(v: number) => industries[Math.round(v)] ?? ''} stroke="var(--axis)" width={110}
                 tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} tickLine={false} reversed />
          <ZAxis range={[90, 90]} />
          <ReferenceLine x={0} stroke="var(--axis)" />
          <Tooltip cursor={false} content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const d = payload[0].payload as (typeof data)[number]
            return (
              <div className="card px-3 py-2 text-xs">
                <div className="font-semibold">{d.ticker} · {label(d.kpi)} <span className="muted">({d.ind})</span></div>
                <div>Skill vs last quarter <b>{signed(d.raw)}</b></div>
                <div className="muted">Mean error {fmt(d.mae, 2)} vs {fmt(d.maeN, 2)} naive</div>
              </div>
            )
          }} />
          <Scatter data={data} isAnimationActive={false}
                   onClick={(d) => onOpen((d as unknown as { ticker: string }).ticker)} cursor="pointer">
            {data.map((d) => (
              <Cell key={`${d.ticker}-${d.kpi}`} fill={d.raw >= 0 ? 'var(--pos)' : 'var(--neg)'}
                    stroke="var(--surface-1)" strokeWidth={2} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer></div>
    </section>
  )
}

export function Portfolio({ data, onOpen }: { data: Scorecard; onOpen: (ticker: string) => void }) {
  const rows: Row[] = useMemo(() => data.twins.flatMap((t) =>
    Object.entries(t.score.kpis).map(([kpi, s]) => ({
      ticker: t.ticker, ind: INDUSTRY_NAMES[t.industry] ?? t.industry, built_by: t.built_by, kpi, s,
    }))), [data])
  const industries = useMemo(() => [...new Set(rows.map((r) => r.ind))].sort(), [rows])
  const [filter, setFilter] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: 'skill_naive', dir: -1 })

  const value = (r: Row, k: SortKey): string | number => {
    if (k === 'ticker' || k === 'ind' || k === 'kpi') return r[k]
    return (r.s[k] ?? -Infinity) as number
  }
  const shown = rows
    .filter((r) => !filter || r.ind === filter)
    .filter((r) => !query || r.ticker.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => {
      const va = value(a, sort.key), vb = value(b, sort.key)
      return (va < vb ? -1 : va > vb ? 1 : 0) * sort.dir
    })
  const beatsNaive = rows.filter((r) => (r.s.skill_naive ?? -1) > 0).length
  const beatsSeasonal = rows.filter((r) => (r.s.skill_seasonal ?? -1) > 0).length
  const factory = data.twins.filter((t) => t.built_by === 'factory').length

  const Th = ({ k, children }: { k: SortKey; children: React.ReactNode }) => (
    <th aria-sort={sort.key === k ? (sort.dir === 1 ? 'ascending' : 'descending') : 'none'}>
      <button onClick={() => setSort({ key: k, dir: sort.key === k ? (-sort.dir as 1 | -1) : -1 })}>
        {children}{sort.key === k ? (sort.dir === 1 ? ' ↑' : ' ↓') : ''}
      </button>
    </th>
  )

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile i={0} labelText={`twins across ${industries.length} industries`} note={`${factory} built by the factory from a ticker`}>
          <CountUp value={data.twins.length} />
        </Tile>
        <Tile i={1} labelText="KPI series where the twin beats last quarter" note="CRPS, walk-forward, no lookahead">
          <CountUp value={beatsNaive} /> <span className="text-xl muted">/ {rows.length}</span>
        </Tile>
        <Tile i={2} labelText="beat the same quarter last year">
          <CountUp value={beatsSeasonal} /> <span className="text-xl muted">/ {rows.length}</span>
        </Tile>
        <Tile i={3} labelText="first test quarter" note="refit at every release on data public at that moment">
          {data.test_from}
        </Tile>
      </div>

      <Reveal i={4}><SkillStrip rows={rows} onOpen={onOpen} /></Reveal>

      <Reveal i={5}>
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by industry">
          <button className="chip" aria-pressed={filter === null} onClick={() => setFilter(null)}>All industries</button>
          {industries.map((i) => (
            <button key={i} className="chip" aria-pressed={filter === i} onClick={() => setFilter(i)}>{i}</button>
          ))}
          <input className="search ml-auto" placeholder="Search ticker…" value={query} aria-label="Search ticker"
                 onChange={(e) => setQuery(e.target.value)} />
        </div>
      </Reveal>

      <Reveal i={6}>
        <div className="card overflow-x-auto p-2">
          <table className="data w-full">
            <thead>
              <tr>
                <Th k="ticker">Ticker</Th><Th k="ind">Industry</Th><th>Built by</th><Th k="kpi">KPI</Th><th>Quarters</th>
                <Th k="mae_twin">Mean error, twin</Th><th>…last quarter</th><th>…same qtr last year</th>
                <Th k="skill_naive">Skill vs last quarter</Th><Th k="skill_seasonal">Skill vs last year</Th>
                <Th k="coverage80">80% interval hit rate</Th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={`${r.ticker}-${r.kpi}`} className="clickable" onClick={() => onOpen(r.ticker)}
                    tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') onOpen(r.ticker) }}>
                  <td className="font-semibold">{r.ticker}</td>
                  <td className="secondary">{r.ind}</td>
                  <td className="secondary">{r.built_by}</td>
                  <td>{label(r.kpi)}</td>
                  <td>{r.s.n}</td>
                  <td>{fmt(r.s.mae_twin, 2)}</td>
                  <td className="secondary">{fmt(r.s.mae_naive, 2)}</td>
                  <td className="secondary">{fmt(r.s.mae_seasonal, 2)}</td>
                  <td><Skill v={r.s.skill_naive} /></td>
                  <td><Skill v={r.s.skill_seasonal} /></td>
                  <td>{r.s.coverage80 == null ? '–' : `${Math.round(r.s.coverage80 * 100)}%`}</td>
                </tr>
              ))}
              {shown.length === 0 && <tr><td colSpan={11} className="muted">No twin matches “{query}”.</td></tr>}
            </tbody>
          </table>
        </div>
      </Reveal>
      <p className="text-xs muted">
        Skill = 1 − CRPS(twin) / CRPS(baseline); positive means the twin is better. Mean errors are in KPI points.
        COVID quarters and spec-declared regime breaks are excluded from scoring. Generated {data.generated}.
      </p>
    </div>
  )
}
