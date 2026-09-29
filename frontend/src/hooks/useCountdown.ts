/**
 * Live countdown to a moment in the future.
 *
 * The deadline arrives as an ISO string, so the tick is computed in the browser
 * and no request is made while it runs.
 */

import { useEffect, useState } from 'react'

const TICK_MS = 1000

/** Minutes left until `target`, rounded up. `null` when there is no target. */
export function useCountdownMinutes(target: string | null | undefined): number | null {
  const deadline = toTimestamp(target)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (deadline === null) return undefined
    // Starts on mount and whenever the target changes, then stops itself once the
    // deadline passes. The first tick is one second later, which is invisible.
    const timer = window.setInterval(() => {
      const current = Date.now()
      setNow(current)
      if (current >= deadline) window.clearInterval(timer)
    }, TICK_MS)
    return () => window.clearInterval(timer)
  }, [deadline])

  if (deadline === null) return null
  return Math.max(0, Math.ceil((deadline - now) / 60_000))
}

/** Minutes a duration in seconds represents, for "cada N min". */
export function toMinutes(seconds: number): number {
  return Math.max(0, Math.round(seconds / 60))
}

function toTimestamp(value: string | null | undefined): number | null {
  if (!value) return null
  const parsed = new Date(value).getTime()
  return Number.isNaN(parsed) ? null : parsed
}
