import { useEffect, useRef, useState } from 'react'
import { emit, type ChatAction } from './bus'

type ToolCall = { name: string; summary: string }
type Msg = { role: 'user' | 'assistant'; text: string; calls?: ToolCall[]; actions?: ChatAction[]; error?: boolean }

const STARTERS = [
  'How does the twin factory build a company from a ticker?',
  'What happens to airlines if jet fuel rises 30%?',
  'Simulate a food-safety scare at Chipotle.',
  'Is the twin better than analysts?',
]

async function send(message: string, sessionId: string | null) {
  const r = await fetch('/api/chat', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(body.detail ?? `${r.status}`)
  return body as { session_id: string; reply: string; tool_calls: ToolCall[]; actions: ChatAction[] }
}

function actionLabel(a: ChatAction): string {
  return a.type === 'open_twin'
    ? `Show ${a.ticker}${a.shocks.length ? ' with this scenario' : ''}`
    : 'Show this economy shock'
}

export function ChatPanel({ onOpenTwin, onOpenPortfolio }: { onOpenTwin: (t: string) => void; onOpenPortfolio: () => void }) {
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [session, setSession] = useState<string | null>(null)
  const [status, setStatus] = useState<{ configured: boolean; model: string } | null>(null)
  const end = useRef<HTMLDivElement>(null)

  useEffect(() => { fetch('/api/chat/status').then((r) => r.json()).then(setStatus).catch(() => setStatus(null)) }, [])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])

  const ask = (text: string) => {
    const q = text.trim()
    if (!q || busy) return
    setMsgs((m) => [...m, { role: 'user', text: q }])
    setInput(''); setBusy(true)
    send(q, session)
      .then((r) => {
        setSession(r.session_id)
        setMsgs((m) => [...m, { role: 'assistant', text: r.reply, calls: r.tool_calls, actions: dedupe(r.actions) }])
      })
      .catch((e) => setMsgs((m) => [...m, { role: 'assistant', text: String(e.message ?? e), error: true }]))
      .finally(() => setBusy(false))
  }

  const show = (a: ChatAction) => {
    if (a.type === 'open_twin') onOpenTwin(a.ticker)
    else onOpenPortfolio()
    setTimeout(() => emit(a), 50)  // let the view mount, then hand it the action
  }

  return (
    <>
      {!open && (
        <button className="primary fixed bottom-5 right-5 z-40 shadow-lg" style={{ padding: '10px 18px' }}
                onClick={() => setOpen(true)} aria-label="Open the Chui assistant">Ask Chui</button>
      )}
      {open && (
        <aside className="card fade-in fixed bottom-5 right-5 z-40 flex flex-col"
               style={{ width: 'min(420px, calc(100vw - 2.5rem))', height: 'min(620px, calc(100vh - 2.5rem))' }}
               aria-label="Chui assistant">
          <header className="flex items-center justify-between gap-3 border-b px-4 py-3" style={{ borderColor: 'var(--border)' }}>
            <div>
              <div className="serif brand-heading font-semibold">Chui assistant</div>
              <div className="text-xs muted">
                {status?.configured ? `Answers from the twin's own tools · ${status.model}` : 'Not configured yet'}
              </div>
            </div>
            <button className="chip" onClick={() => setOpen(false)} aria-label="Close">Close</button>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm" aria-live="polite">
            {msgs.length === 0 && (
              <div className="space-y-3">
                <p className="secondary">
                  Ask how the system works, run a scenario, or have a forecast explained. Every number comes from
                  the twin's own tools, with sources. It explains; it does not give investment advice.
                </p>
                {status && !status.configured && (
                  <p className="rounded-md p-2 text-xs" style={{ background: 'var(--wash)' }}>
                    To enable it, set <code>ANTHROPIC_API_KEY</code> on the server and restart it.
                  </p>
                )}
                <div className="flex flex-col items-start gap-2">
                  {STARTERS.map((s) => (
                    <button key={s} className="chip text-left" onClick={() => ask(s)} disabled={busy}>{s}</button>
                  ))}
                </div>
              </div>
            )}
            {msgs.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'flex justify-end' : ''}>
                <div className="max-w-[90%] rounded-lg px-3 py-2"
                     style={m.role === 'user'
                       ? { background: 'var(--brand)', color: 'var(--brand-ink)' }
                       : { background: 'var(--wash)', color: m.error ? 'var(--bad-text)' : 'var(--text-primary)' }}>
                  <div className="whitespace-pre-wrap">{m.text}</div>
                  {!!m.calls?.length && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {m.calls.map((c, j) => (
                        <span key={j} className="rounded-full px-2 py-0.5 text-[11px] muted"
                              style={{ border: '1px solid var(--border)' }} title={c.name}>Ran: {c.summary}</span>
                      ))}
                    </div>
                  )}
                  {!!m.actions?.length && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {m.actions.map((a, j) => <button key={j} className="chip" onClick={() => show(a)}>{actionLabel(a)}</button>)}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {busy && <p className="muted">Thinking and running the twin…</p>}
            <div ref={end} />
          </div>

          <form className="flex gap-2 border-t px-3 py-3" style={{ borderColor: 'var(--border)' }}
                onSubmit={(e) => { e.preventDefault(); ask(input) }}>
            <input className="search flex-1" value={input} onChange={(e) => setInput(e.target.value)}
                   placeholder="Ask about a twin or a scenario…" aria-label="Message" disabled={busy} />
            <button className="primary" type="submit" disabled={busy || !input.trim()}>Send</button>
          </form>
        </aside>
      )}
    </>
  )
}

function dedupe(actions: ChatAction[]): ChatAction[] {
  const seen = new Set<string>()
  return actions.filter((a) => { const k = JSON.stringify(a); if (seen.has(k)) return false; seen.add(k); return true })
}
