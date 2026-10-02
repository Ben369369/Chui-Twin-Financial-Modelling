import { useMemo, useState } from 'react'
import { fmt, label, signed, type Scorecard } from './api'

const INDUSTRY_NAMES: Record<string, string> = {
  restaurant: 'Restaurants', restaurants: 'Restaurants', airline: 'Airlines', airlines: 'Airlines',
  hotels: 'Hotels', homebuilders: 'Homebuilders', general_retail: 'General retail',
}

function Skill({ v }: { v: number | null }) {
  // Glyph + sign + value: color is never the only cue.
  if (v == null) return <span className="muted">–</span>
  const good = v > 0
  return (
    <span style={{ color: good ? 'var(--good-text)' : 'var(--bad-text)' }}>
      {good ? '▲' : '▼'} {signed(v)}
    </span>
  )
}

function Tile({ value, label, note }: { value: string; label: string; note?: string }) {
  return (
    <div className="card p-4">
      <div className="text-3xl font-semibold">{value}</div>
      <div className="mt-1 text-sm secondary">{label}</div>
      {note && <div className="mt-1 text-xs muted">{note}</div>}
    </div>
  )
}

export function Portfolio({ data, onOpen }: { data: Scorecard; onOpen: (ticker: string) => void }) {
  const industries = useMemo(
    () => [...new Set(data.twins.map((t) => INDUSTRY_NAMES[t.industry] ?? t.industry))].sort(),
    [data],
  )
  const [filter, setFilter] = useState<string | null>(null)

  const rows = data.twins.flatMap((t) =>
    Object.entries(t.score.kpis).map(([kpi, s]) => ({ ...t, ind: INDUSTRY_NAMES[t.industry] ?? t.industry, kpi, s })),
  )
  const shown = rows.filter((r) => !filter || r.ind === filter)
  const beatsNaive = rows.filter((r) => (r.s.skill_naive ?? -1) > 0).length
  const beatsSeasonal = rows.filter((r) => (r.s.skill_seasonal ?? -1) > 0).length
  const factory = data.twins.filter((t) => t.built_by === 'factory').length

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile value={String(data.twins.length)} label={`twins across ${industries.length} industries`}
              note={`${factory} built by the factory from a ticker`} />
        <Tile value={`${beatsNaive} / ${rows.length}`} label="KPI series where the twin beats last quarter"
              note="CRPS, walk-forward" />
        <Tile value={`${beatsSeasonal} / ${rows.length}`} label="beat same quarter last year" />
        <Tile value={data.test_from} label="first test quarter"
              note="refit at every release on data public at that moment" />
      </div>

      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by industry">
        <button className="chip" aria-pressed={filter === null} onClick={() => setFilter(null)}>All industries</button>
        {industries.map((i) => (
          <button key={i} className="chip" aria-pressed={filter === i} onClick={() => setFilter(i)}>{i}</button>
        ))}
      </div>

      <div className="card overflow-x-auto p-2">
        <table className="data w-full">
          <thead>
            <tr>
              <th>Ticker</th><th>Industry</th><th>Built by</th><th>KPI</th><th>Quarters</th>
              <th>Mean error, twin</th><th>…last quarter</th><th>…same qtr last year</th>
              <th>Skill vs last quarter</th><th>Skill vs last year</th><th>80% interval hit rate</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={`${r.ticker}-${r.kpi}`}>
                <td>
                  <button className="font-semibold underline decoration-dotted underline-offset-2"
                          onClick={() => onOpen(r.ticker)}>{r.ticker}</button>
                </td>
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
          </tbody>
        </table>
      </div>
      <p className="text-xs muted">
        Skill = 1 − CRPS(twin) / CRPS(baseline); positive means the twin is better. Mean errors are in KPI points.
        COVID quarters and spec-declared regime breaks are excluded from scoring. Generated {data.generated}.
      </p>
    </div>
  )
}
