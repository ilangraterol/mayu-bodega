import { Link } from 'react-router-dom'

import { StatCardSkeleton } from '../components/ui/Skeleton'
import { EmptyState, ErrorState } from '../components/ui/Feedback'
import { Card, DualAmount, StockBadge } from '../components/ui/Primitives'
import { ProductImage } from '../components/products/ProductImage'
import { useDebts } from '../hooks/useDebts'
import { useProducts } from '../hooks/useProducts'
import { useSales, useSalesSummary } from '../hooks/useSales'
import { formatDate, formatRelative } from '../lib/date'
import { formatUsd, formatVes, parseMoney } from '../lib/money'
import { PAYMENT_METHOD_LABELS } from '../lib/labels'

export function DashboardPage() {
  const summary = useSalesSummary()
  const debts = useDebts({ openOnly: true, pageSize: 5 })
  const sales = useSales({ today: true, pageSize: 5 })
  const lowStock = useProducts({ lowStock: true, pageSize: 5 })

  return (
    <div className="space-y-4">
      <section aria-labelledby="today-heading">    
        {summary.isLoading ? (
          <div className="grid grid-cols-2 gap-2">
            <StatCardSkeleton />
            <StatCardSkeleton />
          </div>
        ) : summary.isError ? (
          <Card>
            <ErrorState
              error={summary.error}
              onRetry={summary.refetch}
              title="No pudimos cargar el resumen"
            />
          </Card>
        ) : summary.data ? (
          <div className="grid grid-cols-2 gap-2">
            <Card className="p-3">
              <p className="text-xs text-slate-500">Ventas de hoy</p>
              <DualAmount usd={summary.data.total_usd} size="lg" />
              <p className="mt-1 text-[11px] text-slate-400">
                {summary.data.sales_count} ventas · {summary.data.credit_sales_count} fiadas
              </p>
            </Card>
            <Card className="p-3">
              <p className="text-xs text-slate-500">Crédito por cobrar</p>
              <DualAmount usd={summary.data.pending_debt_usd} size="lg" />
              <p className="mt-1 text-[11px] text-slate-400">
                {summary.data.open_debts_count} deudas abiertas
              </p>
            </Card>
          </div>
        ) : null}
      </section>

      <section aria-labelledby="low-stock-heading">
        <div className="mb-2 flex items-baseline justify-between">
          <h2 id="low-stock-heading" className="text-base font-semibold text-slate-900">
            stock bajo
          </h2>
          <Link to="/productos?low=1" className="text-xs font-medium text-slate-500 underline">
            Ver todo
          </Link>
        </div>
        <Card>
          {lowStock.isLoading ? (
            <div className="space-y-2 p-3">
              {Array.from({ length: 3 }, (_, index) => (
                <StatCardSkeleton key={index} />
              ))}
            </div>
          ) : lowStock.isError ? (
            <ErrorState error={lowStock.error} onRetry={lowStock.refetch} />
          ) : (lowStock.data?.results.length ?? 0) === 0 ? (
            <EmptyState
              icon="✅"
              title="Todo con existencias"
              description="Ningún producto está por debajo de su empaque."
            />
          ) : (
            <ul className="divide-y divide-slate-100">
              {lowStock.data!.results.map((product) => (
                <li key={product.id} className="flex items-center gap-3 p-2.5">
                  <div className="size-11 shrink-0 overflow-hidden rounded-lg">
                    <ProductImage src={product.primary_image_url} alt={product.name} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-800">{product.name}</p>
                    <p className="tabular text-xs text-slate-500">
                      {formatUsd(product.price_usd)}
                    </p>
                  </div>
                  <StockBadge stock={product.stock} pending={product.pending_units} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      <section aria-labelledby="debts-heading">
        <div className="mb-2 flex items-baseline justify-between">
          <h2 id="debts-heading" className="text-base font-semibold text-slate-900">
            deudas abiertas
          </h2>
          <Link to="/creditos" className="text-xs font-medium text-slate-500 underline">
            Ver todo
          </Link>
        </div>
        <Card>
          {debts.isLoading ? (
            <div className="space-y-2 p-3">
              {Array.from({ length: 3 }, (_, index) => (
                <StatCardSkeleton key={index} />
              ))}
            </div>
          ) : debts.isError ? (
            <ErrorState error={debts.error} onRetry={debts.refetch} />
          ) : (debts.data?.results.length ?? 0) === 0 ? (
            <EmptyState
              icon="🎉"
              title="Sin deudas pendientes"
              description="Todos los clientes están al día."
            />
          ) : (
            <ul className="divide-y divide-slate-100">
              {debts.data!.results.map((debt) => (
                <li key={debt.id} className="flex items-center justify-between gap-3 p-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-800">
                      {debt.customer_name}
                    </p>
                    <p className="truncate text-xs text-slate-500">
                      {debt.sale_code} · {formatDate(debt.sale_date)}
                    </p>
                  </div>
                  <span className="tabular shrink-0 text-sm font-semibold text-amber-700">
                    {formatUsd(debt.balance_usd)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      <section aria-labelledby="recent-heading">
        <div className="mb-2 flex items-baseline justify-between">
          <h2 id="recent-heading" className="text-base font-semibold text-slate-900">
            ventas recientes
          </h2>
          <Link to="/ventas" className="text-xs font-medium text-slate-500 underline">
            Ver todo
          </Link>
        </div>
        <Card>
          {sales.isLoading ? (
            <div className="space-y-2 p-3">
              {Array.from({ length: 3 }, (_, index) => (
                <StatCardSkeleton key={index} />
              ))}
            </div>
          ) : sales.isError ? (
            <ErrorState error={sales.error} onRetry={sales.refetch} />
          ) : (sales.data?.results.length ?? 0) === 0 ? (
            <EmptyState
              icon="🧾"
              title="Sin ventas hoy"
              description="Registra la primera venta del día."
              action={
                <Link
                  to="/vender"
                  className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white"
                >
                  Ir a vender
                </Link>
              }
            />
          ) : (
            <ul className="divide-y divide-slate-100">
              {sales.data!.results.map((sale) => (
                <li key={sale.id} className="p-3">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-sm font-medium text-slate-800">{sale.code}</span>
                    <span className="shrink-0 text-right">
                      <span className="tabular block text-sm font-semibold text-slate-900">
                        {formatUsd(sale.total_usd)}
                      </span>
                      <span className="tabular block text-[11px] text-slate-400">
                        {formatVes(sale.total_ves)}
                      </span>
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center justify-between gap-3 text-xs text-slate-500">
                    <span>
                      {sale.customer_name ?? 'Cliente mostrador'} ·{' '}
                      {PAYMENT_METHOD_LABELS[sale.payment_method] ?? sale.payment_method}
                    </span>
                    <span>{formatRelative(sale.created_at)}</span>
                  </div>
                  {parseMoney(sale.amount_due_usd) > 0 ? (
                    <p className="tabular mt-1 text-xs font-medium text-amber-700">
                      Debe {formatUsd(sale.amount_due_usd)}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>
    </div>
  )
}
