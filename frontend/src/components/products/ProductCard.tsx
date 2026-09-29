/** Product card for the point-of-sale grid. */

import { formatUsd } from '../../lib/money'
import type { Product } from '../../types/api'
import { Badge, StockBadge } from '../ui/Primitives'
import { ProductImage } from './ProductImage'

interface ProductCardProps {
  product: Product
  /** Units already in the cart; shown as a corner badge. */
  inCart: number
  onSelect: (product: Product) => void
  disabled?: boolean
}

export function ProductCard({ product, inCart, onSelect, disabled }: ProductCardProps) {
  const pending = Number.parseFloat(product.pending_units || '0')

  return (
    <button
      type="button"
      onClick={() => onSelect(product)}
      disabled={disabled}
      className="relative flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white text-left transition-transform active:scale-[0.97] disabled:opacity-50"
    >
      {inCart > 0 ? (
        <span className="absolute top-1.5 right-1.5 z-10 flex size-6 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white">
          {inCart}
        </span>
      ) : null}

      <div className="relative">
        <ProductImage src={product.primary_image_url} alt={product.name} />
        {pending > 0 ? (
          <span className="absolute bottom-1.5 left-1.5">
            <Badge tone="danger">Debe {pending}</Badge>
          </span>
        ) : null}
      </div>

      <div className="flex flex-1 flex-col gap-1 p-2">
        <span className="line-clamp-2 text-xs leading-tight font-medium text-slate-800">
          {product.name}
        </span>
        {product.brand ? (
          <span className="truncate text-[11px] text-slate-400">{product.brand}</span>
        ) : null}
        <div className="mt-auto flex items-center justify-between gap-1 pt-1">
          <span className="tabular text-sm font-semibold text-slate-900">
            {formatUsd(product.price_usd)}
          </span>
          <StockBadge stock={product.stock} pending={product.pending_units} />
        </div>
      </div>
    </button>
  )
}
