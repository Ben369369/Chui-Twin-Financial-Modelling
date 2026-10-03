// Tiny action bus: the chat asks a view to show something (open a twin with a scenario, run an
// economy shock). The view may not be mounted yet, so the last action is also kept until taken.

export type ChatAction =
  | { type: 'open_twin'; ticker: string; shocks: { primitive: string; period: string; size: number; halfLife: number }[] }
  | { type: 'economy_shock'; series: string; move: number }

let pending: ChatAction | null = null
const EVENT = 'chui-action'

export function emit(action: ChatAction) {
  pending = action
  window.dispatchEvent(new CustomEvent(EVENT, { detail: action }))
}

/** Take the pending action if it is of this type (and for this ticker, when given). */
export function take<T extends ChatAction['type']>(type: T, ticker?: string): Extract<ChatAction, { type: T }> | null {
  const a = pending
  if (!a || a.type !== type) return null
  if (ticker && a.type === 'open_twin' && a.ticker !== ticker) return null
  pending = null
  return a as Extract<ChatAction, { type: T }>
}

export function listen(fn: () => void): () => void {
  window.addEventListener(EVENT, fn)
  return () => window.removeEventListener(EVENT, fn)
}
