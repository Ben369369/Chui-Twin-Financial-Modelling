import { useEffect, useRef, useState } from 'react'

/** The Chui Trading logo block from the letterhead: navy square, white wordmark set right. */
export function ChuiLogo({ size = 56 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" role="img" aria-label="Chui Trading">
      <rect width="100" height="100" fill="var(--brand)" />
      <text x="88" y="58" textAnchor="end" fill="var(--brand-ink)" fontFamily="system-ui, -apple-system, 'Segoe UI', sans-serif"
            fontSize="26" fontWeight="500">Chui</text>
      <text x="88" y="80" textAnchor="end" fill="var(--brand-ink)" fontFamily="system-ui, -apple-system, 'Segoe UI', sans-serif"
            fontSize="17" fontWeight="400">Trading</text>
    </svg>
  )
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )
  useEffect(() => {
    const m = window.matchMedia('(prefers-reduced-motion: reduce)')
    const on = () => setReduced(m.matches)
    m.addEventListener('change', on)
    return () => m.removeEventListener('change', on)
  }, [])
  return reduced
}

/** Counts up to `value` once on mount (and when it changes). Static under reduced motion. */
export function CountUp({ value, decimals = 0, duration = 900 }: { value: number; decimals?: number; duration?: number }) {
  const reduced = usePrefersReducedMotion()
  const [shown, setShown] = useState(reduced ? value : 0)
  const from = useRef(0)
  useEffect(() => {
    if (reduced) { setShown(value); return }
    const start = performance.now()
    const a = from.current
    let raf = 0
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / duration)
      const eased = 1 - Math.pow(1 - k, 3)
      setShown(a + (value - a) * eased)
      if (k < 1) raf = requestAnimationFrame(tick)
      else from.current = value
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, duration, reduced])
  return <>{shown.toFixed(decimals)}</>
}

/** Wraps children in a staggered rise-in. */
export function Reveal({ i = 0, className = '', children }: { i?: number; className?: string; children: React.ReactNode }) {
  return (
    <div className={`reveal ${className}`} style={{ ['--delay' as string]: `${i * 70}ms` }}>
      {children}
    </div>
  )
}
