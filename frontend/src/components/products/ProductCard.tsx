/** Product card for the point-of-sale grid. */

import { formatUsdCompact } from '../../lib/money'
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

      <div className="flex flex-1 flex-col gap-0.5 p-1.5">
        {/* The brand is skipped: it already reads as part of the name, and on a
            mobile grid every line is space that could show another product.
            The name is not clamped, because a truncated product name is worse
            than a card that is slightly taller: the cashier cannot tell two
            similar products apart. */}
        <span className="text-[11px] leading-tight font-medium break-words text-slate-800">
          {product.name}
        </span>
        <div className="mt-auto flex items-center justify-between gap-0.5 pt-0.5">
          <span className="tabular text-xs font-semibold text-slate-900">
            {formatUsdCompact(product.price_usd)}
          </span>
          {/* The badge is shared with wider layouts, so the tighter padding is
              applied here: inside a four-column phone grid every pixel of the
              price row is contested. */}
          <span className="[&>span]:px-1.5 [&>span]:text-[11px]">
            <StockBadge
              stock={product.stock}
              pending={product.pending_units}
              compact
            />
          </span>
        </div>
      </div>
    </button>
  )
}
