/** Sales history: filter by type and status, and void a mistaken sale. */

import { useState } from 'react'

import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState } from '../components/ui/Feedback'
import { TextInput } from '../components/ui/Field'
import { ListSkeleton } from '../components/ui/Skeleton'
import { Card, StatusBadge } from '../components/ui/Primitives'
import { Sheet } from '../components/ui/Sheet'
import { useSales, useVoidSale } from '../hooks/useSales'
import { formatDate, formatDateTime } from '../lib/date'
import { PAYMENT_METHOD_LABELS } from '../lib/labels'
import { formatUsd, formatVes } from '../lib/money'
import { SALE_STATUS, SALE_TYPE } from '../types/api'
import type { Sale } from '../types/api'

export function SalesPage() {
  const [saleType, setSaleType] = useState('')
  const [status, setStatus] = useState('')
  const [search, setSearch] = useState('')
  const [voiding, setVoiding] = useState<Sale | null>(null)

  const sales = useSales({
    saleType: saleType || undefined,
    status: status || undefined,
    search: search.trim() || undefined,
    pageSize: 50,
  })

  return (
    <div className="space-y-3">
      <TextInput
        label="Buscar venta"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Código, cliente o nota"
        autoCapitalize="none"
      />

      <div className="no-scrollbar -mx-1 flex gap-1.5 overflow-x-auto px-1">
        {[
          { value: '', label: 'Todas' },
          { value: SALE_TYPE.PAID, label: 'Pagadas' },
          { value: SALE_TYPE.CREDIT, label: 'Fiadas' },
          { value: SALE_STATUS.ANULLED, label: 'Anuladas' },
        ].map((item) => (
          <button
            key={item.label}
            type="button"
            onClick={() => {
              setSaleType(item.value === SALE_TYPE.PAID || item.value === SALE_TYPE.CREDIT ? item.value : '')
              setStatus(item.value === SALE_STATUS.ANULLED ? SALE_STATUS.ANULLED : '')
            }}
            className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium ${
              (saleType || status) === item.value
                ? 'bg-slate-900 text-white'
                : 'border border-slate-300 bg-white text-slate-600'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {sales.isLoading ? (
        <Card>
          <ListSkeleton count={8} />
        </Card>
      ) : sales.isError ? (
        <Card>
          <ErrorState error={sales.error} onRetry={sales.refetch} />
        </Card>
      ) : (sales.data?.results.length ?? 0) === 0 ? (
        <Card>
          <EmptyState
            icon="🧾"
            title="Sin ventas"
            description="No hay ventas que coincidan con el filtro."
          />
        </Card>
      ) : (
        <Card>
          <ul className="divide-y divide-slate-100">
            {sales.data!.results.map((sale) => (
              <li key={sale.id} className="p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm font-semibold text-slate-800">{sale.code}</span>
                      <StatusBadge status={sale.status} />
                      {sale.sale_type === SALE_TYPE.CREDIT ? (
                        <StatusBadge status={SALE_TYPE.CREDIT} />
                      ) : null}
                    </div>
                    <p className="truncate text-xs text-slate-500">
                      {sale.customer_name ?? 'Cliente mostrador'} ·{' '}
                      {PAYMENT_METHOD_LABELS[sale.payment_method] ?? sale.payment_method}
                    </p>
                    <p className="text-[11px] text-slate-400">
                      {formatDate(sale.sale_date)} · {sale.items.length} art. · {sale.created_by}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="tabular text-sm font-semibold text-slate-900">
                      {formatUsd(sale.total_usd)}
                    </p>
                    <p className="tabular text-[11px] text-slate-400">{formatVes(sale.total_ves)}</p>
                    {sale.status === SALE_STATUS.COMPLETED ? (
                      <button
                        type="button"
                        onClick={() => setVoiding(sale)}
                        className="mt-0.5 text-[11px] text-slate-400 underline active:text-red-600"
                      >
                        anular
                      </button>
                    ) : null}
                  </div>
                </div>
                {sale.status === SALE_STATUS.ANULLED && sale.void_reason ? (
                  <p className="mt-1.5 rounded bg-red-50 px-2 py-1 text-[11px] text-red-800">
                    Anulada {formatDateTime(sale.voided_at)}: {sale.void_reason}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <VoidSheet sale={voiding} onClose={() => setVoiding(null)} />
    </div>
  )
}

function VoidSheet({ sale, onClose }: { sale: Sale | null; onClose: () => void }) {
  const voidSale = useVoidSale()
  const [reason, setReason] = useState('')

  return (
    <Sheet
      open={sale !== null}
      onClose={onClose}
      title={`Anular ${sale?.code ?? ''}`}
      footer={
        <Button
          variant="danger"
          fullWidth
          size="lg"
          isLoading={voidSale.isPending}
          disabled={reason.trim().length < 5 || !sale}
          onClick={async () => {
            if (!sale) return
            try {
              await voidSale.mutate({ id: sale.id, reason: reason.trim() })
              setReason('')
              onClose()
            } catch {
              // Banner shows the reason.
            }
          }}
        >
          Anular venta
        </Button>
      }
    >
      <div className="space-y-3">
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
          La venta no se borra: queda anulada y el stock se devuelve. Si el producto tenía
          unidades pendientes, la deuda de inventario también se cancela.
        </p>
        <TextInput
          label="Motivo de la anulación"
          required
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Mínimo 5 caracteres"
        />
        {voidSale.error ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            {voidSale.error.detail}
          </p>
        ) : null}
      </div>
    </Sheet>
  )
}
