/**
 * Server-calculated cart totals. Never computed on the client.
 *
 * Each line carries its own surcharge, so a single percentage over the subtotal
 * would be a lie. The breakdown is therefore per line, and the headline
 * percentage is only shown as the subtotal-weighted average the sale records.
 */

import { formatPercent, formatRate, formatUsd, formatVes, parseMoney } from '../../lib/money'
import { SURCHARGE_SOURCE } from '../../types/api'
import type { Quote } from '../../types/api'

const SOURCE_LABELS: Record<string, string> = {
  [SURCHARGE_SOURCE.PRODUCT]: 'del artículo',
  [SURCHARGE_SOURCE.CATEGORY]: 'de la categoría',
  [SURCHARGE_SOURCE.STORE]: 'de la tienda',
  [SURCHARGE_SOURCE.MANUAL]: 'elegido en el carrito',
}

export function QuoteSummary({ quote }: { quote: Quote }) {
  const hasSurcharge = parseMoney(quote.surcharge_usd) > 0
  const chargedLines = quote.lines.filter(
    (line) => parseMoney(line.surcharge_percentage) > 0,
  )

  return (
    <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
      <div className="flex justify-between">
        <span className="text-slate-500">Subtotal</span>
        <span className="tabular">{formatUsd(quote.subtotal_usd)}</span>
      </div>

      {hasSurcharge ? (
        <div className="mt-1.5 space-y-1">
          {chargedLines.map((line) => (
            <div key={line.product_id} className="flex justify-between gap-2 text-xs">
              <span className="min-w-0 truncate text-slate-500">
                {line.product_name}{' '}
                <span className="tabular">+{formatPercent(line.surcharge_percentage)}</span>{' '}
                <span className="text-slate-400">
                  {SOURCE_LABELS[line.surcharge_source] ?? ''}
                </span>
              </span>
              <span className="tabular shrink-0 text-slate-600">
                {formatUsd(line.surcharge_usd)}
              </span>
            </div>
          ))}
          <div className="flex justify-between border-t border-slate-200 pt-1 text-slate-500">
            <span>
              Recargo <span className="tabular">{formatPercent(quote.surcharge_percentage)}</span>{' '}
              prom.
            </span>
            <span className="tabular">{formatUsd(quote.surcharge_usd)}</span>
          </div>
        </div>
      ) : null}

      <div className="mt-1 flex justify-between border-t border-slate-200 pt-1 font-semibold">
        <span>Total</span>
        <span className="tabular">{formatUsd(quote.total_usd)}</span>
      </div>
      <div className="mt-0.5 flex justify-between text-xs text-slate-500">
        <span>Tasa {formatRate(quote.exchange_rate_applied)}</span>
        <span className="tabular">{formatVes(quote.total_ves)}</span>
      </div>
    </div>
  )
}
