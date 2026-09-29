import { useCallback, useEffect, useMemo, useState } from 'react'

import { ProductCard } from '../components/products/ProductCard'
import { CartRow } from '../components/sales/CartRow'
import { CheckoutSheet } from '../components/sales/CheckoutSheet'
import { QuoteSummary } from '../components/sales/QuoteSummary'
import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState } from '../components/ui/Feedback'
import { TextInput } from '../components/ui/Field'
import { ProductGridSkeleton } from '../components/ui/Skeleton'
import { Badge, Card } from '../components/ui/Primitives'
import { Sheet } from '../components/ui/Sheet'
import { useBarcodeScanner } from '../hooks/useBarcodeScanner'
import { useCart } from '../hooks/useCart'
import { useProducts } from '../hooks/useProducts'
import { useQuote, useSalesSummary } from '../hooks/useSales'
import { useStoreConfig } from '../hooks/useCustomers'
import { formatUsd, parseMoney } from '../lib/money'
import type { Product, Quote } from '../types/api'

type Filter = 'todos' | 'agotados' | 'deuda'

export function SellPage() {
  const cart = useCart()
  const storeConfig = useStoreConfig()
  const summary = useSalesSummary()

  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState<Filter>('todos')
  const [page, setPage] = useState(1)
  const [isCartOpen, setIsCartOpen] = useState(false)
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false)

  const products = useProducts({
    search: search.trim() || undefined,
    outOfStock: filter === 'agotados',
    page,
    pageSize: 60,
  })

  const onScanned = useCallback((product: Product) => cart.add(product), [cart])
  const scanner = useBarcodeScanner({ onResolved: onScanned })

  useEffect(() => {
    setPage(1)
  }, [search, filter])

  // "Con deuda" has no server-side filter, so it narrows the current page.
  const visibleProducts = useMemo(() => {
    const results = products.data?.results ?? []
    if (filter !== 'deuda') return results
    return results.filter((product) => parseMoney(product.pending_units) > 0)
  }, [products.data, filter])

  const quote = useQuote()
  const [quoteData, setQuoteData] = useState<Quote | null>(null)

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
  }, [cart.isEmpty, JSON.stringify(cart.lines)])

  // Debounce so tapping +/- does not fire a request per tap.
  useEffect(() => {
    const timer = setTimeout(refreshQuote, 400)
    return () => clearTimeout(timer)
  }, [refreshQuote])

  const filters = useMemo(
    () => [
      { value: 'todos', label: 'Todos' },
      { value: 'agotados', label: 'Agotados' },
      { value: 'deuda', label: 'Con deuda' },
    ],
    [],
  )

  return (
    <div className="space-y-3">
      <div className="sticky top-14 z-20 -mx-3 space-y-2 bg-slate-100/95 px-3 py-2 backdrop-blur">
        <form onSubmit={scanner.onSubmit} className="relative">
          <TextInput
            label="Buscar o escanear"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value)
              scanner.setCode(event.target.value)
            }}
            placeholder="Nombre, código o código de barras"
            autoCapitalize="none"
          />
          {scanner.isResolving ? (
            <span className="absolute top-8 right-3 size-4 animate-spin rounded-full border-2 border-slate-400 border-t-transparent" />
          ) : null}
        </form>

        {scanner.notFound ? (
          <p className="text-xs text-red-600" role="alert">
            No encontramos «{scanner.code}».
          </p>
        ) : null}

        <div className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1">
          {filters.map((item) => (
            <button
              key={item.value}
              type="button"
              onClick={() => setFilter(item.value as Filter)}
              className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium ${
                filter === item.value
                  ? 'bg-slate-900 text-white'
                  : 'border border-slate-300 bg-white text-slate-600'
              }`}
            >
              {item.label}
            </button>
          ))}
          {storeConfig.data && !storeConfig.data.allow_zero_stock_sale ? (
            <span className="shrink-0 self-center pl-1 text-[11px] text-amber-700">
              Sin stock no se vende
            </span>
          ) : null}
        </div>
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
                : filter === 'deuda'
                  ? 'Ningún producto tiene unidades pendientes.'
                  : 'El catálogo está vacío. Registra productos para empezar a vender.'
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
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

      {summary.data ? (
        <p className="pb-1 text-center text-[11px] text-slate-400">
          Hoy: {summary.data.sales_count} ventas por {formatUsd(summary.data.total_usd)}
        </p>
      ) : null}

      {/* Persistent cart bar: within thumb reach on every screen size. */}
      {cart.count > 0 ? (
        <div className="pb-safe fixed inset-x-0 bottom-14 z-30 border-t border-slate-200 bg-white px-3 pt-2">
          <div className="mx-auto flex w-full max-w-3xl items-center gap-2">
            <button
              type="button"
              onClick={() => setIsCartOpen(true)}
              className="flex min-w-0 flex-1 items-center gap-2 text-left"
            >
              <Badge tone="neutral">{cart.count}</Badge>
              <span className="truncate text-xs text-slate-500">
                {cart.lines.length} prod.
              </span>
              <span className="tabular ml-auto text-lg font-bold text-slate-900">
                {formatUsd(quoteData?.total_usd ?? String(cart.estimatedSubtotalUsd))}
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
          products.refetch()
          summary.refetch()
        }}
      />
    </div>
  )
}
