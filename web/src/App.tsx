import { useEffect, useState } from 'react'
import { api, loadSeriesLabels, type Scorecard, type TwinSummary } from './api'
import { ChuiLogo } from './brand'
import { ChatPanel } from './ChatPanel'
import { Portfolio } from './Portfolio'
import { TwinView } from './TwinView'

type View = 'portfolio' | 'twin'
type Theme = 'light' | 'dark' | 'system'

// Linkable views: #/portfolio or #/twin/CMG
function readHash(): { view: View; ticker: string } {
  const [, v, t] = window.location.hash.split('/')
  return v === 'twin' ? { view: 'twin', ticker: (t || 'CMG').toUpperCase() } : { view: 'portfolio', ticker: 'CMG' }
}

function loadTheme(): Theme {
  try {
    const t = localStorage.getItem('chui-theme')
    return t === 'light' || t === 'dark' ? t : 'system'
  } catch {
    return 'system'
  }
}

export default function App() {
  const initial = readHash()
  const [view, setViewState] = useState<View>(initial.view)
  const [twins, setTwins] = useState<TwinSummary[]>([])
  const [score, setScore] = useState<Scorecard | null>(null)
  const [ticker, setTickerState] = useState(initial.ticker)
  const [err, setErr] = useState<string | null>(null)
  const [theme, setTheme] = useState<Theme>(loadTheme)

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
    try { localStorage.setItem('chui-theme', theme) } catch { /* storage unavailable: theme still applies */ }
  }, [theme])

  useEffect(() => {
    const onHash = () => { const h = readHash(); setViewState(h.view); setTickerState(h.ticker) }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = (v: View, t: string) => {
    setViewState(v); setTickerState(t)
    window.location.hash = v === 'twin' ? `/twin/${t}` : '/portfolio'
  }
  const setView = (v: View) => go(v, ticker)
  const setTicker = (t: string) => go('twin', t)

  useEffect(() => {
    loadSeriesLabels()
    api.twins().then(setTwins).catch((e) => setErr(String(e)))
    api.scorecard().then(setScore).catch((e) => setErr(String(e)))
  }, [])

  const nextTheme: Record<Theme, Theme> = { system: 'light', light: 'dark', dark: 'system' }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <header className="mb-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <ChuiLogo size={60} />
            <div>
              <h1 className="serif brand-heading text-3xl font-semibold leading-tight">Chui Twin</h1>
              <p className="text-sm secondary">Public companies as runnable operating models · every number traced to its source</p>
            </div>
          </div>
          <nav className="flex items-center gap-2" aria-label="Views">
            <button className="chip" aria-pressed={view === 'portfolio'} onClick={() => setView('portfolio')}>Portfolio</button>
            <button className="chip" aria-pressed={view === 'twin'} onClick={() => setView('twin')}>Twin</button>
            <button className="chip" onClick={() => setTheme(nextTheme[theme])} aria-label={`Theme: ${theme}. Click to change.`}
                    title="Theme">{theme === 'dark' ? '◐ Dark' : theme === 'light' ? '◑ Light' : '◒ Auto'}</button>
          </nav>
        </div>
        <p className="mt-3 text-center text-xs italic secondary">Chui Trading · A Chui Labs company · Princeton, NJ</p>
        <div className="rule-draw mt-1 h-px" style={{ background: 'var(--brand)' }} />
      </header>

      {err && <p className="mb-4 text-sm" style={{ color: 'var(--bad-text)' }}>API error: {err}. Is `uvicorn api.serve:app` running?</p>}

      <main key={view} className="fade-in">
        {view === 'portfolio'
          ? (score ? <Portfolio data={score} onOpen={setTicker} /> : <p className="muted">Loading scorecard…</p>)
          : <TwinView ticker={ticker} twins={twins} onTicker={setTicker} />}
      </main>

      <ChatPanel onOpenTwin={(t) => go('twin', t)} onOpenPortfolio={() => go('portfolio', ticker)} />

      <footer className="mt-10 border-t pt-4 text-center text-xs muted" style={{ borderColor: 'var(--border)' }}>
        Chui Twin is built by Chui Trading, part of Chui Labs, for the Longaeva AI Hackathon.
        A research tool, not investment advice.
      </footer>
    </div>
  )
}
