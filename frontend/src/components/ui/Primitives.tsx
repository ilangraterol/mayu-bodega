/** Small presentational pieces shared across screens. */

import type { ReactNode } from 'react'

import { formatUsd, formatVes, parseMoney, roundMoney } from '../../lib/money'
import { CURRENCY_VES } from '../../types/api'

export function Card({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white ${className}`}>{children}</div>
  )
}

type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info'

const TONES: Record<BadgeTone, string> = {
  neutral: 'bg-slate-100 text-slate-700',
  success: 'bg-emerald-100 text-emerald-800',
  warning: 'bg-amber-100 text-amber-900',
  danger: 'bg-red-100 text-red-800',
  info: 'bg-sky-100 text-sky-800',
}

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: BadgeTone
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      {children}
    </span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { tone: BadgeTone; label: string }> = {
    COMPLETED: { tone: 'success', label: 'Completada' },
    PAID: { tone: 'success', label: 'Pagada' },
    OPEN: { tone: 'warning', label: 'Pendiente' },
    ANULLED: { tone: 'danger', label: 'Anulada' },
    CREDIT: { tone: 'info', label: 'Fiada' },
  }
  const entry = map[status] ?? { tone: 'neutral' as BadgeTone, label: status }
  return <Badge tone={entry.tone}>{entry.label}</Badge>
}

/**
 * Stock pill that also surfaces the pending (shortage) balance.
 *
 * `compact` swaps the words for the bare number so the till grid can show the
 * real stock figure ("0" instead of "Agotado") in a fraction of the width; the
 * wording is kept everywhere else, where there is room to read it.
 */
export function StockBadge({
  stock,
  pending,
  compact = false,
}: {
  stock: string
  pending?: string
  compact?: boolean
}) {
  const stockValue = parseMoney(stock)
  const pendingValue = parseMoney(pending ?? '0')
  if (pendingValue > 0) {
    return (
      <Badge tone="danger">
        {compact ? `0 · ${pendingValue}` : `0 · debe ${pendingValue}`}
      </Badge>
    )
  }
  if (stockValue <= 0) {
    return (
      <Badge tone="danger">
        {compact ? '0' : 'Agotado'}
      </Badge>
    )
  }
  if (stockValue < 1) {
    return (
      <Badge tone="warning">
        {compact ? '<1' : 'Últimas'}
      </Badge>
    )
  }
  return <Badge tone="neutral">{stockValue}</Badge>
}

/** Money in the primary currency with theVES equivalent underneath. */
export function DualAmount({
  usd,
  ves,
  size = 'md',
}: {
  usd: string
  ves?: string
  size?: 'sm' | 'md' | 'lg'
}) {
  const sizes = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-2xl',
  }
  return (
    <span className="tabular inline-flex flex-col items-end">
      <span className={`font-semibold text-slate-900 ${sizes[size]}`}>{formatUsd(usd)}</span>
      {ves ? (
        <span className={`text-slate-500 ${size === 'lg' ? 'text-sm' : 'text-xs'}`}>
          {formatVes(ves)}
        </span>
      ) : null}
    </span>
  )
}

/** Renders both currencies on one line, used in dense tables. */
export function MoneyCell({ amount, currency }: { amount: string; currency: string }) {
  return (
    <span className="tabular whitespace-nowrap">
      {currency === CURRENCY_VES ? formatVes(amount) : formatUsd(amount)}
    </span>
  )
}

export function Divider({ label }: { label?: string }) {
  if (!label) return <hr className="border-slate-200" />
  return (
    <div className="flex items-center gap-2 text-xs font-medium text-slate-400 uppercase">
      <hr className="flex-1 border-slate-200" />
      {label}
      <hr className="flex-1 border-slate-200" />
    </div>
  )
}

export function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="tabular font-medium text-slate-900">{children}</span>
    </div>
  )
}

/** Percentage badge for the configured surcharge. */
export function SurchargeBadge({ value }: { value: string }) {
  const percent = roundMoney(parseMoney(value), 2)
  if (percent === 0) return null
  return <Badge tone="warning">+{percent}% recargo</Badge>
}
