/** Credit ledger: open debts, partial payments in VES/USD, and reversals. */

import { useMemo, useState } from 'react'

import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState, SuccessBanner } from '../components/ui/Feedback'
import { NumberInput, Select, TextInput } from '../components/ui/Field'
import { ListSkeleton, StatCardSkeleton } from '../components/ui/Skeleton'
import { Card, MoneyCell, StatusBadge } from '../components/ui/Primitives'
import { Sheet } from '../components/ui/Sheet'
import { useAddDebtPayment, useDebts } from '../hooks/useDebts'
import { useCurrentRate } from '../hooks/useRates'
import { formatDate, formatDateTime, toDateTimeInput } from '../lib/date'
import { PAYMENT_METHOD_LABELS, USD_METHODS, VES_METHODS } from '../lib/labels'
import { formatRate, formatUsd, parseMoney, toMoneyString } from '../lib/money'
import { CURRENCY_USD, CURRENCY_VES } from '../types/api'
import type { Currency, CustomerDebt, DebtPayment, PaymentMethod } from '../types/api'

type Scope = 'abiertas' | 'todas'

export function CreditsPage() {
  const [scope, setScope] = useState<Scope>('abiertas')
  const [search, setSearch] = useState('')
  const [paying, setPaying] = useState<CustomerDebt | null>(null)

  const debts = useDebts({
    openOnly: scope === 'abiertas',
    search: search.trim() || undefined,
    pageSize: 50,
  })

  const total = useMemo(
    () =>
      (debts.data?.results ?? []).reduce(
        (sum, debt) => sum + parseMoney(debt.balance_usd),
        0,
      ),
    [debts.data],
  )

  return (
    <div className="space-y-3">
      <TextInput
        label="Buscar cliente"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Nombre, cédula o código de venta"
        autoCapitalize="none"
      />

      <div className="flex items-center justify-between gap-2">
        <div className="flex gap-1.5">
          {(['abiertas', 'todas'] as Scope[]).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setScope(item)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                scope === item
                  ? 'bg-slate-900 text-white'
                  : 'border border-slate-300 bg-white text-slate-600'
              }`}
            >
              {item === 'abiertas' ? 'Abiertas' : 'Todas'}
            </button>
          ))}
        </div>
        {debts.data ? (
          <span className="tabular text-sm font-semibold text-slate-900">
            {formatUsd(total)}
          </span>
        ) : null}
      </div>

      {debts.isLoading ? (
        <Card>
          <ListSkeleton count={6} />
        </Card>
      ) : debts.isError ? (
        <Card>
          <ErrorState error={debts.error} onRetry={debts.refetch} />
        </Card>
      ) : (debts.data?.results.length ?? 0) === 0 ? (
        <Card>
          <EmptyState
            icon="📒"
            title={scope === 'abiertas' ? 'Sin deudas abiertas' : 'Sin registro'}
            description={
              scope === 'abiertas'
                ? 'Todos los clientes están al día.'
                : 'No hay ventas fiadas registradas.'
            }
          />
        </Card>
      ) : (
        <Card>
          <ul className="divide-y divide-slate-100">
            {debts.data!.results.map((debt) => (
              <li key={debt.id}>
                <button
                  type="button"
                  onClick={() => setPaying(debt)}
                  className="flex w-full items-center justify-between gap-3 p-3 text-left"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-800">
                      {debt.customer_name}
                    </p>
                    <p className="truncate text-xs text-slate-500">
                      {debt.sale_code} · {formatDate(debt.sale_date)}
                      {debt.payments.filter((payment) => !payment.is_voided).length > 0
                        ? ` · ${debt.payments.filter((p) => !p.is_voided).length} abono(s)`
                        : ''}
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="tabular text-sm font-semibold text-amber-700">
                      {formatUsd(debt.balance_usd)}
                    </p>
                    <div className="mt-0.5 flex justify-end">
                      <StatusBadge status={debt.status} />
                    </div>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <PaymentSheet debt={paying} onClose={() => setPaying(null)} />
    </div>
  )
}

function PaymentSheet({ debt, onClose }: { debt: CustomerDebt | null; onClose: () => void }) {
  const rate = useCurrentRate()
  const addPayment = useAddDebtPayment()

  const [currency, setCurrency] = useState<Currency>(CURRENCY_USD)
  const [method, setMethod] = useState<PaymentMethod>('CASH_USD')
  const [amount, setAmount] = useState('')
  const [paidAt, setPaidAt] = useState(() => toDateTimeInput())
  const [notes, setNotes] = useState('')
  const [done, setDone] = useState<string | null>(null)

  const balance = parseMoney(debt?.balance_usd ?? '0')
  const entered = parseMoney(amount)
  // The backend converts with the rate of the payment date; the screen shows
  // the same figure using the current rate as an estimate.
  const suggested =
    currency === CURRENCY_VES && rate.data ? balance * parseMoney(rate.data.rate) : balance

  function reset(nextCurrency: Currency) {
    setCurrency(nextCurrency)
    setMethod(nextCurrency === CURRENCY_VES ? 'CASH_VES' : 'CASH_USD')
    setAmount(nextCurrency === CURRENCY_VES ? toMoneyString(suggested) : toMoneyString(balance))
    setDone(null)
    addPayment.reset()
  }

  const options =
    currency === CURRENCY_VES
      ? VES_METHODS.map((value) => ({ value, label: PAYMENT_METHOD_LABELS[value] }))
      : USD_METHODS.map((value) => ({ value, label: PAYMENT_METHOD_LABELS[value] }))

  const remaining = balance - (currency === CURRENCY_VES ? entered / parseMoney(rate.data?.rate ?? '1') : entered)
  const exceeds = currency === CURRENCY_USD ? entered > balance : remaining < 0

  async function onSubmit() {
    if (!debt) return
    try {
      const result = await addPayment.mutate({
        debtId: debt.id,
        payload: {
          amount: toMoneyString(entered),
          currency,
          method,
          // `datetime-local` has no timezone; the API expects ISO-8601.
          paid_at: new Date(paidAt).toISOString(),
          notes,
        },
      })
      setDone(`Abono registrado. Saldo: ${formatUsd(result.debt.balance_usd)}`)
      setAmount('')
      setNotes('')
    } catch {
      // Rendered by the error banner.
    }
  }

  return (
    <Sheet
      open={debt !== null}
      onClose={onClose}
      title={debt ? `Abono · ${debt.customer_name}` : 'Abono'}
      footer={
        <Button
          variant="success"
          size="lg"
          fullWidth
          isLoading={addPayment.isPending}
          disabled={entered <= 0 || exceeds}
          onClick={onSubmit}
        >
          Registrar abono
        </Button>
      }
    >
      {debt ? (
        <div className="space-y-3">
          {done ? <SuccessBanner>{done}</SuccessBanner> : null}

          <div className="rounded-lg bg-slate-50 p-3 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-500">Venta</span>
              <span className="tabular">{debt.sale_code}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Fecha</span>
              <span>{formatDate(debt.sale_date)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Monto original</span>
              <span className="tabular">{formatUsd(debt.original_amount_usd)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Abonado</span>
              <span className="tabular">{formatUsd(debt.paid_amount_usd)}</span>
            </div>
            <div className="mt-1 flex justify-between border-t border-slate-200 pt-1 font-semibold">
              <span>Saldo</span>
              <span className="tabular text-amber-700">{formatUsd(debt.balance_usd)}</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => reset(CURRENCY_USD)}
              className={`rounded-lg border px-3 py-2.5 text-sm font-medium ${
                currency === CURRENCY_USD
                  ? 'border-slate-900 bg-slate-900 text-white'
                  : 'border-slate-300 bg-white text-slate-700'
              }`}
            >
              Dollars
            </button>
            <button
              type="button"
              onClick={() => reset(CURRENCY_VES)}
              className={`rounded-lg border px-3 py-2.5 text-sm font-medium ${
                currency === CURRENCY_VES
                  ? 'border-slate-900 bg-slate-900 text-white'
                  : 'border-slate-300 bg-white text-slate-700'
              }`}
            >
              Bolívares
            </button>
          </div>

          <Select
            label="Método"
            value={method}
            onChange={(event) => setMethod(event.target.value as PaymentMethod)}
            options={options}
          />

          <NumberInput
            label={`Monto del abono (${currency})`}
            required
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            hint={
              currency === CURRENCY_VES && rate.data
                ? `Equivale a ${formatUsd(entered / parseMoney(rate.data.rate))} a tasa ${formatRate(rate.data.rate)}`
                : undefined
            }
          />

          <TextInput
            label="Fecha del abono"
            type="datetime-local"
            value={paidAt}
            onChange={(event) => setPaidAt(event.target.value)}
            max={toDateTimeInput()}
          />

          <TextInput
            label="Notas"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Opcional"
          />

          {exceeds ? (
            <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
              El abono supera el saldo pendiente de {formatUsd(balance)}.
            </p>
          ) : null}

          <PaymentHistory payments={debt.payments} />

          <ErrorOrNotice error={addPayment.error} />
        </div>
      ) : (
        <div className="space-y-2">
          <StatCardSkeleton />
        </div>
      )}
    </Sheet>
  )
}

function PaymentHistory({ payments }: { payments: DebtPayment[] }) {
  const active = payments.filter((payment) => !payment.is_voided)
  if (active.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 px-3 py-3 text-center text-xs text-slate-500">
        Esta deuda no tiene abonos registrados.
      </p>
    )
  }
  return (
    <div>
      <h3 className="mb-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase">
        historial de abonos
      </h3>
      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200">
        {payments.map((payment) => (
          <li
            key={payment.id}
            className={`flex items-center justify-between gap-2 px-3 py-2 text-sm ${
              payment.is_voided ? 'opacity-50' : ''
            }`}
          >
            <div className="min-w-0">
              <p className="truncate">
                {PAYMENT_METHOD_LABELS[payment.method] ?? payment.method}
                {payment.is_voided ? ' · anulado' : ''}
              </p>
              <p className="text-[11px] text-slate-500">
                {formatDateTime(payment.paid_at)} · tasa {formatRate(payment.exchange_rate_applied)}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <MoneyCell amount={payment.amount} currency={payment.currency} />
              <p className="text-[11px] text-slate-400">= {formatUsd(payment.amount_usd)}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ErrorOrNotice({ error }: { error: { detail: string | null } | null }) {
  if (!error) return null
  return (
    <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
      {error.detail}
    </p>
  )
}
