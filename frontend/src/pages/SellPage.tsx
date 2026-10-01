import { useCallback, useEffect, useState } from 'react'

import { CreditCard, ScanSearch } from 'lucide-react'
import { CategoryChips } from '../components/catalog/CategoryChips'
import { ProductCard } from '../components/products/ProductCard'
import { CartRow } from '../components/sales/CartRow'
import { CheckoutSheet } from '../components/sales/CheckoutSheet'
import { QuoteSummary } from '../components/sales/QuoteSummary'
import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState } from '../components/ui/Feedback'
import { ProductGridSkeleton } from '../components/ui/Skeleton'
import { Card } from '../components/ui/Primitives'
import { Sheet } from '../components/ui/Sheet'
import { useBarcodeScanner } from '../hooks/useBarcodeScanner'
import { useCart } from '../hooks/useCart'
import { useCategoryOptions } from '../hooks/useCategories'
import { useProducts } from '../hooks/useProducts'
import { useQuote } from '../hooks/useSales'
import { useStoreConfig } from '../hooks/useCustomers'
import { formatUsd } from '../lib/money'
import type { Product, Quote } from '../types/api'

export function SellPage() {
  const cart = useCart()
  const storeConfig = useStoreConfig()

  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [isCartOpen, setIsCartOpen] = useState(false)
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false)

  const categories = useCategoryOptions()

  const products = useProducts({
    search: search.trim() || undefined,
    category,
    page,
    pageSize: 60,
  })

  const onScanned = useCallback((product: Product) => cart.add(product), [cart])
  const scanner = useBarcodeScanner({ onResolved: onScanned })

  useEffect(() => {
    setPage(1)
  }, [search, category])

  const visibleProducts = products.data?.results ?? []

  const quote = useQuote()
  const [quoteData, setQuoteData] = useState<Quote | null>(null)

  // The payload drives the quote, so a per-line surcharge change has to be part
  // of the dependency: editing a percentage must reprice the cart.
  const payloadKey = JSON.stringify(cart.toPayload())

  const refreshQuote = useCallback(() => {
    if (cart.isEmpty) {
      setQuoteData(null)
      return
    }
    quote
      .mutate(cart.toPayload())
      .then(setQuoteData)
      .catch(() => setQuoteData(null))
    // `quote.mutate` is stable for the lifetime of the mutation hook.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cart.isEmpty, payloadKey])

  // Debounce so tapping +/- does not fire a request per tap.
  useEffect(() => {
    const timer = setTimeout(refreshQuote, 400)
    return () => clearTimeout(timer)
  }, [refreshQuote])

  return (
    // The fixed cart bar stacks on top of the bottom nav, so the page needs
    // extra room below the grid while the bar is showing.
    <div className={`space-y-2 ${cart.count > 0 ? 'pb-28' : ''}`}>
      {/* Pulled up against the header: the cashier's first action is typing or
          scanning, and the slack above the field was wasted vertical space. */}
      <div className="sticky top-header-offset z-20 -mx-3 -mt-1 space-y-1 bg-slate-100/95 px-2 pt-1.5 pb-1.5 backdrop-blur">
        <form onSubmit={scanner.onSubmit} className="relative">
          <div className="relative">
            <ScanSearch
              aria-hidden="true"
              className="animate-float motion-reduce:animate-none pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-slate-500"
            />
            <input
              value={search}
              onChange={(event) => {
                // Typing filters the grid; it must not feed the barcode scanner,
                // or every partial word 404s on `barcode_lookup` and the till
                // reports "not found" while results are on screen.
                setSearch(event.target.value)
                scanner.setCode(event.target.value)
                scanner.clearNotFound()
              }}
              placeholder="Buscar Producto"
              autoCapitalize="none"
              className="w-full min-h-11 rounded-lg border border-slate-300 bg-white pl-9 pr-3 text-base text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none focus:ring-1 focus:ring-slate-900"
            />
          </div>
          {scanner.isResolving ? (
            <span className="absolute right-3 top-1/2 size-4 -translate-y-1/2 animate-spin rounded-full border-2 border-slate-400 border-t-transparent" />
          ) : null}
        </form>

        {scanner.notFound ? (
          <p className="text-xs text-red-600" role="alert">
            {/* The scanned code is cleared on failure, so the alert stands on its
                own instead of quoting an empty string. */}
            Ese código de barras no existe en el catálogo.
          </p>
        ) : null}

        {storeConfig.data && !storeConfig.data.allow_zero_stock_sale ? (
          <p className="text-[11px] text-amber-700">Sin stock no se vende</p>
        ) : null}

        <CategoryChips
          categories={categories.data?.results ?? []}
          value={category}
          onChange={setCategory}
        />
      </div>

      {products.isLoading ? (
        <ProductGridSkeleton count={10} />
      ) : products.isError ? (
        <Card>
          <ErrorState
            error={products.error}
            onRetry={products.refetch}
            title="No pudimos cargar el catálogo"
          />
        </Card>
      ) : visibleProducts.length === 0 ? (
        <Card>
          <EmptyState
            icon="🔍"
            title="Sin resultados"
            description={
              search
                ? `Ningún producto coincide con «${search}».`
                : category
                  ? 'Esta categoría no tiene productos disponibles.'
                  : 'El catálogo está vacío. Registra productos para empezar a vender.'
            }
          />
        </Card>
      ) : (
        // Three columns on a phone, not four: at four the card is ~81px wide and a
        // 43-character name needs four lines to appear whole, which pushes the
        // price off screen. Three fits the full name and the price together.
        <div className="grid grid-cols-3 gap-1 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6">
          {visibleProducts.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              inCart={cart.quantityOf(product.id)}
              onSelect={(selected) => {
                cart.add(selected)
                if (navigator.vibrate) navigator.vibrate(8)
              }}
            />
          ))}
        </div>
      )}

      {products.data && products.data.count > visibleProducts.length ? (
        <div className="flex items-center justify-center gap-3 py-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setPage((value) => value - 1)}
            disabled={page === 1}
          >
            Anterior
          </Button>
          <span className="tabular text-xs text-slate-500">
            {visibleProducts.length} de {products.data.count}
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setPage((value) => value + 1)}
            disabled={!products.data.next}
          >
            Siguiente
          </Button>
        </div>
      ) : null}

      {/* Persistent cart bar: within thumb reach on every screen size. */}
      {cart.count > 0 ? (
        <div className="pb-safe fixed inset-x-0 bottom-14 z-30 border-t border-slate-200 bg-white px-3 pt-2">
          <div className="mx-auto flex w-full max-w-3xl items-stretch gap-2">
            {/* The whole card opens the cart, so it is built as a tap target:
                border, fill and a chevron tell the operator it is not a label. */}
            <button
              type="button"
              onClick={() => setIsCartOpen(true)}
              aria-label={`Abrir carrito: ${cart.lines.length} productos, ${cart.count} unidades`}
              className="flex min-w-0 flex-1 items-center gap-2 rounded-xl border border-slate-300 bg-slate-50 px-2.5 py-2 text-left active:bg-slate-100"
            >
              {/* The card floats continuously. `motion-reduce` turns it off for
                  users who ask for less movement. */}
              <CreditCard
                aria-hidden="true"
                className="animate-float motion-reduce:animate-none size-5 shrink-0 text-slate-600"
              />
              <span className="min-w-0 flex-1">
                <span className="block text-xs font-medium text-slate-800">
                  Ver carrito
                </span>
                <span className="tabular block truncate text-[11px] text-slate-500">
                  {cart.lines.length} prod. · {cart.count} uds.
                </span>
              </span>
              <span className="tabular shrink-0 text-base font-bold text-slate-900">
                {formatUsd(quoteData?.total_usd ?? String(cart.estimatedSubtotalUsd))}
              </span>
              <span aria-hidden="true" className="shrink-0 text-slate-400">
                ›
              </span>
            </button>
            <Button
              variant="success"
              size="lg"
              onClick={() => setIsCheckoutOpen(true)}
              disabled={cart.hasShortage && !storeConfig.data?.allow_zero_stock_sale}
            >
              Cobrar
            </Button>
          </div>
        </div>
      ) : null}

      <Sheet
        open={isCartOpen}
        onClose={() => setIsCartOpen(false)}
        title="Carrito"
        footer={
          <div className="flex gap-2">
            <Button variant="secondary" fullWidth onClick={cart.clear}>
              Vaciar
            </Button>
            <Button
              variant="success"
              fullWidth
              onClick={() => {
                setIsCartOpen(false)
                setIsCheckoutOpen(true)
              }}
              disabled={cart.isEmpty}
            >
              Cobrar {formatUsd(quoteData?.total_usd ?? '0')}
            </Button>
          </div>
        }
      >
        {cart.isEmpty ? (
          <EmptyState
            icon="🛒"
            title="Carrito vacío"
            description="Toca un producto para agregarlo."
          />
        ) : (
          <ul className="divide-y divide-slate-100">
            {cart.lines.map((line) => (
              <CartRow
                key={line.product.id}
                line={line}
                onIncrement={() => cart.increment(line.product.id)}
                onDecrement={() => cart.decrement(line.product.id)}
                onRemove={() => cart.remove(line.product.id)}
                onSurchargeChange={(percentage) => cart.setSurcharge(line.product.id, percentage)}
                allowZeroStock={storeConfig.data?.allow_zero_stock_sale ?? false}
              />
            ))}
          </ul>
        )}

        {quoteData ? <QuoteSummary quote={quoteData} /> : null}
      </Sheet>

      <CheckoutSheet
        open={isCheckoutOpen}
        onClose={() => setIsCheckoutOpen(false)}
        quote={quoteData}
        items={cart.toPayload()}
        onDone={() => {
          cart.clear()
          setQuoteData(null)
          setIsCheckoutOpen(false)
          // The day's total in the header refreshes itself: creating a sale
          // invalidates the `sales-summary` cache key.
          products.refetch()
        }}
      />
    </div>
  )
}
