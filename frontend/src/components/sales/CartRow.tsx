/** A single cart line with quantity steppers and a per-line surcharge picker. */

import { formatQuantity, formatUsd, parseMoney, roundMoney } from '../../lib/money'
import { Badge } from '../ui/Primitives'
import { ProductImage } from '../products/ProductImage'
import { SurchargePicker } from './SurchargePicker'
import type { CartLine } from '../../hooks/useCart'

interface CartRowProps {
  line: CartLine
  onIncrement: () => void
  onDecrement: () => void
  onRemove: () => void
  /** `null` hands the percentage back to the catalogue. */
  onSurchargeChange: (percentage: number | null) => void
  /** When false, the store blocks selling more than the physical stock. */
  allowZeroStock: boolean
}

export function CartRow({
  line,
  onIncrement,
  onDecrement,
  onRemove,
  onSurchargeChange,
  allowZeroStock,
}: CartRowProps) {
  const stock = parseMoney(line.product.stock)
  const overStock = line.quantity > stock
  const blocked = overStock && !allowZeroStock
  const unitPrice = parseMoney(line.product.price_usd)
  const lineTotal = line.quantity * unitPrice

  // The surcharge is computed client-side only to show what the line will cost;
  // the server quote stays authoritative for every number that gets charged.
  const percentage = line.surchargePercentage ?? line.inheritedPercentage
  const surcharge = roundMoney((lineTotal * percentage) / 100)

  return (
    <li className="py-2.5">
      <div className="flex items-center gap-2.5">
        <div className="size-12 shrink-0 overflow-hidden rounded-lg">
          <ProductImage src={line.product.primary_image_url} alt={line.product.name} />
        </div>

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-800">{line.product.name}</p>
          <p className="tabular text-xs text-slate-500">{formatUsd(line.product.price_usd)} c/u</p>
          {overStock ? (
            <p className="mt-0.5">
              {allowZeroStock ? (
                <Badge tone="warning">queda en deuda</Badge>
              ) : (
                <Badge tone="danger">solo {formatQuantity(stock)} disponibles</Badge>
              )}
            </p>
          ) : null}
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={onDecrement}
            className="flex size-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-lg leading-none text-slate-700 active:bg-slate-100"
            aria-label={`Quitar una unidad de ${line.product.name}`}
          >
            −
          </button>
          <span className="tabular w-9 text-center text-sm font-semibold">
            {formatQuantity(line.quantity)}
          </span>
          <button
            type="button"
            onClick={onIncrement}
            disabled={blocked}
            className="flex size-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-lg leading-none text-slate-700 active:bg-slate-100 disabled:opacity-40"
            aria-label={`Agregar una unidad de ${line.product.name}`}
          >
            +
          </button>
        </div>

        <div className="w-20 shrink-0 text-right">
          <p className="tabular text-sm font-semibold text-slate-900">{formatUsd(lineTotal)}</p>
          <button
            type="button"
            onClick={onRemove}
            className="text-[11px] text-slate-400 underline active:text-red-600"
          >
            quitar
          </button>
        </div>
      </div>

      <div className="mt-1 pl-14.5">
        <SurchargePicker
          inheritedPercentage={line.inheritedPercentage}
          inheritedSource={line.inheritedSource}
          value={line.surchargePercentage}
          onChange={onSurchargeChange}
        />
        {percentage > 0 ? (
          <p className="tabular mt-0.5 text-[11px] text-slate-500">
            {formatUsd(surcharge)} de recargo · total {formatUsd(roundMoney(lineTotal + surcharge))}
          </p>
        ) : null}
      </div>
    </li>
  )
}
