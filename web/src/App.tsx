import { useEffect, useState } from 'react'
import { api, type Scorecard, type TwinSummary } from './api'
import { Portfolio } from './Portfolio'
import { TwinView } from './TwinView'

type View = 'portfolio' | 'twin'

// Linkable views: #/portfolio or #/twin/CMG
function readHash(): { view: View; ticker: string } {
  const [, v, t] = window.location.hash.split('/')
  return v === 'twin' ? { view: 'twin', ticker: (t || 'CMG').toUpperCase() } : { view: 'portfolio', ticker: 'CMG' }
}

export default function App() {
  const initial = readHash()
  const [view, setViewState] = useState<View>(initial.view)
  const [twins, setTwins] = useState<TwinSummary[]>([])
  const [score, setScore] = useState<Scorecard | null>(null)
  const [ticker, setTickerState] = useState(initial.ticker)
  const [err, setErr] = useState<string | null>(null)

  const go = (v: View, t: string) => {
    setViewState(v); setTickerState(t)
    window.location.hash = v === 'twin' ? `/twin/${t}` : '/portfolio'
  }
  const setView = (v: View) => go(v, ticker)
  const setTicker = (t: string) => go('twin', t)

  useEffect(() => {
    api.twins().then(setTwins).catch((e) => setErr(String(e)))
    api.scorecard().then(setScore).catch((e) => setErr(String(e)))
  }, [])

  const open = (t: string) => go('twin', t)

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Chui Twin</h1>
          <p className="text-sm secondary">Public companies as runnable operating models · every number traced to its source</p>
        </div>
        <nav className="flex gap-2">
          <button className="chip" aria-pressed={view === 'portfolio'} onClick={() => setView('portfolio')}>Portfolio</button>
          <button className="chip" aria-pressed={view === 'twin'} onClick={() => setView('twin')}>Twin</button>
        </nav>
      </header>
      {err && <p className="mb-4 text-sm" style={{ color: 'var(--bad-text)' }}>API error: {err}. Is `uvicorn api.main:app` running?</p>}
      {view === 'portfolio'
        ? (score ? <Portfolio data={score} onOpen={open} /> : <p className="muted">Loading scorecard…</p>)
        : <TwinView ticker={ticker} twins={twins} onTicker={setTicker} />}
    </div>
  )
}
