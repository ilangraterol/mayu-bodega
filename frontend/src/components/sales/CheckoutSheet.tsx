/**
 * Checkout: choose paid vs fiada, the payment method and the amount received.
 *
 * When the customer pays in bolivars the server re-prices the total with the BCV
 * rate, so the screen shows both amounts and asks for the amount in the chosen
 * currency. The client never computes what the customer owes in VES.
 *
 * The sheet body lives in `CheckoutForm`, which is mounted only while the sheet
 * is open and keyed by the cart. That makes every value below start from a clean
 * default, so no effect is needed to reset the form between sales.
 */

import { useMemo, useState } from 'react'

import { useCustomers } from '../../hooks/useCustomers'
import { useCreateSale } from '../../hooks/useSales'
import {
  digitsToAmount,
  formatRate,
  formatUsd,
  formatVes,
  nextAmountDigits,
  parseMoney,
  roundMoney,
  toMoneyString,
} from '../../lib/money'
import { PAYMENT_METHOD_LABELS, USD_METHODS, VES_METHODS } from '../../lib/labels'
import { CURRENCY_USD, CURRENCY_VES, SALE_TYPE } from '../../types/api'
import type { Currency, PaymentMethod, Quote, SaleItemInput, SaleType } from '../../types/api'
import { Button } from '../ui/Button'
import { ErrorBanner, SuccessBanner } from '../ui/Feedback'
import { NumberInput, Select, TextInput } from '../ui/Field'
import { Sheet } from '../ui/Sheet'
import { QuoteSummary } from './QuoteSummary'

interface CheckoutSheetProps {
  open: boolean
  onClose: () => void
  quote: Quote | null
  items: SaleItemInput[]
  onDone: () => void
}

const USD_METHOD_OPTIONS = USD_METHODS.map((value) => ({
  value,
  label: PAYMENT_METHOD_LABELS[value],
}))

const VES_METHOD_OPTIONS = VES_METHODS.map((value) => ({
  value,
  label: PAYMENT_METHOD_LABELS[value],
}))

const DEFAULT_METHOD: Record<Currency, PaymentMethod> = {
  [CURRENCY_USD]: 'CASH_USD',
  [CURRENCY_VES]: 'CASH_VES',
}

/** Keeps the method compatible with the currency, because the backend rejects mismatches. */
function methodForCurrency(currency: Currency, current: PaymentMethod): PaymentMethod {
  const allowed = currency === CURRENCY_VES ? VES_METHODS : USD_METHODS
  return allowed.includes(current) ? current : DEFAULT_METHOD[currency]
}

export function CheckoutSheet({ open, onClose, quote, items, onDone }: CheckoutSheetProps) {
  if (!open || !quote) return null

  // A different cart remounts the form, so no field leaks into the next sale.
  // The surcharge is part of the key: changing a line's percentage changes the
  // total, and the amount received has to fall back to the new default.
  const cartKey = `${items.length}:${items
    .map((item) => `${item.product_id}-${item.quantity}-${item.surcharge_percentage ?? 'auto'}`)
    .join(',')}`

  return (
    <CheckoutForm
      key={cartKey}
      quote={quote}
      items={items}
      onClose={onClose}
      onDone={onDone}
    />
  )
}

interface CheckoutFormProps {
  quote: Quote
  items: SaleItemInput[]
  onClose: () => void
  onDone: () => void
}

function CheckoutForm({ quote, items, onClose, onDone }: CheckoutFormProps) {
  const [customerSearch, setCustomerSearch] = useState('')
  // Only credit sales need a customer, so the list is not fetched while paying.
  const customers = useCustomers({ search: customerSearch || undefined, pageSize: 50 })

  const [saleType, setSaleType] = useState<SaleType>(SALE_TYPE.PAID)
  const [currency, setCurrency] = useState<Currency>(CURRENCY_USD)
  const [method, setMethod] = useState<PaymentMethod>('CASH_USD')
  const [paidAmount, setPaidAmount] = useState(() => toMoneyString(quote.total_usd))
  const [customerId, setCustomerId] = useState<number | null>(null)
  const [notes, setNotes] = useState('')
  const [confirmation, setConfirmation] = useState<string | null>(null)

  const createSale = useCreateSale()

  const totalUsd = parseMoney(quote.total_usd)
  const totalVes = parseMoney(quote.total_ves)
  const expected = currency === CURRENCY_VES ? totalVes : totalUsd
  const paid = parseMoney(paidAmount)
  const change = roundMoney(paid - expected)
  const isCredit = saleType === SALE_TYPE.CREDIT

  function onCurrencyChange(next: Currency) {
    setCurrency(next)
    setMethod((current) => methodForCurrency(next, current))
    // The amount received starts at the total in the chosen currency, so the
    // cashier does not have to type it. Both figures come from the server quote:
    // the client never decides what the customer owes in VES.
    setPaidAmount(toMoneyString(next === CURRENCY_VES ? quote.total_ves : quote.total_usd))
  }

  /**
   * In VES the field is filled by digits, so the cashier types "45784" and sees
   * "457.84" grow as they type. `paidAmount` is always the formatted amount, and
   * its digits are the input, which keeps one source of truth for the value the
   * API receives.
   */
  function onVesAmountChange(rawValue: string) {
    setPaidAmount(digitsToAmount(nextAmountDigits(paidAmount, rawValue)))
  }

  const canSubmit = useMemo(() => {
    if (items.length === 0) return false
    if (isCredit) return customerId !== null
    if (currency === CURRENCY_VES) return paid > 0
    // In USD the backend requires an explicit amount; a short payment is a
    // partial payment, which the domain treats as credit.
    return paid >= totalUsd
  }, [items.length, isCredit, customerId, paid, currency, totalUsd])

  const customerOptions = useMemo(
    () =>
      (customers.data?.results ?? []).map((customer) => ({
        value: String(customer.id),
        label: `${customer.name}${customer.document_id ? ` · ${customer.document_id}` : ''}`,
      })),
    [customers.data],
  )

  async function onSubmit() {
    try {
      const sale = await createSale.mutate({
        sale_type: saleType,
        customer_id: isCredit ? customerId : null,
        currency: isCredit ? CURRENCY_USD : currency,
        paid_amount: isCredit ? null : toMoneyString(paid),
        payment_method: method,
        notes,
        items,
      })
      setConfirmation(`Venta ${sale.code} registrada.`)
      // Give the cashier a moment to read the code before the cart resets.
      setTimeout(onDone, 900)
    } catch {
      // The error banner from the mutation hook shows the failure.
    }
  }

  return (
    <Sheet
      open
      onClose={onClose}
      title="Cobrar"
      footer={
        <Button
          variant="success"
          size="lg"
          fullWidth
          isLoading={createSale.isPending}
          disabled={!canSubmit}
          onClick={onSubmit}
        >
          {isCredit ? 'Registrar fiada' : 'Confirmar pago'}
        </Button>
      }
    >
      {confirmation ? (
        <SuccessBanner>{confirmation}</SuccessBanner>
      ) : (
        <div className="space-y-4">
          <QuoteSummary quote={quote} />

          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setSaleType(SALE_TYPE.PAID)}
              className={`rounded-lg border px-3 py-2.5 text-sm font-medium ${
                saleType === SALE_TYPE.PAID
                  ? 'border-slate-900 bg-slate-900 text-white'
                  : 'border-slate-300 bg-white text-slate-700'
              }`}
            >
              Pagada
            </button>
            <button
              type="button"
              onClick={() => setSaleType(SALE_TYPE.CREDIT)}
              className={`rounded-lg border px-3 py-2.5 text-sm font-medium ${
                saleType === SALE_TYPE.CREDIT
                  ? 'border-slate-900 bg-slate-900 text-white'
                  : 'border-slate-300 bg-white text-slate-700'
              }`}
            >
              Fiada
            </button>
          </div>

          {isCredit ? (
            <>
              <TextInput
                label="Buscar cliente"
                value={customerSearch}
                onChange={(event) => setCustomerSearch(event.target.value)}
                placeholder="Nombre, cédula o teléfono"
                autoCapitalize="none"
              />
              <Select
                label="Cliente"
                required
                value={customerId === null ? '' : String(customerId)}
                onChange={(event) => setCustomerId(Number(event.target.value) || null)}
                options={customerOptions}
                placeholder={customers.isLoading ? 'Cargando clientes…' : 'Seleccione un cliente'}
              />
              <p className="text-xs text-slate-500">
                La deuda se guarda en dólares. Al pagarla en bolívares se recalcula con la tasa
                del día del abono.
              </p>
            </>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => onCurrencyChange(CURRENCY_USD)}
                  className={`rounded-lg border px-3 py-2.5 text-sm font-medium ${
                    currency === CURRENCY_USD
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-300 bg-white text-slate-700'
                  }`}
                >
                  Dólares
                </button>
                <button
                  type="button"
                  onClick={() => onCurrencyChange(CURRENCY_VES)}
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
                label="Método de pago"
                value={method}
                onChange={(event) => setMethod(event.target.value as PaymentMethod)}
                options={currency === CURRENCY_VES ? VES_METHOD_OPTIONS : USD_METHOD_OPTIONS}
              />

              {currency === CURRENCY_VES ? (
                <TextInput
                  label="Monto recibido (VES)"
                  required
                  value={paidAmount}
                  onChange={(event) => onVesAmountChange(event.target.value)}
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="0.00"
                  hint="Solo dígitos: 104 se vuelve 1.04 y 45784 se vuelve 457.84."
                />
              ) : (
                <NumberInput
                  label="Monto recibido (USD)"
                  required
                  value={paidAmount}
                  onChange={(event) => setPaidAmount(event.target.value)}
                  step="0.01"
                />
              )}

              <div className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="text-slate-500">Total a cobrar</span>
                <span className="tabular font-semibold">
                  {currency === CURRENCY_VES ? formatVes(totalVes) : formatUsd(totalUsd)}
                </span>
              </div>

              {currency === CURRENCY_VES ? (
                <p className="text-xs text-slate-500">
                  Tasa aplicada {formatRate(quote.exchange_rate_applied)} · equivalente{' '}
                  {formatUsd(totalUsd)}
                </p>
              ) : null}

              {change > 0 ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                  Cambio a entregar:{' '}
                  <span className="tabular font-semibold">
                    {currency === CURRENCY_VES ? formatVes(change) : formatUsd(change)}
                  </span>
                </div>
              ) : null}

              {paid > 0 && paid < expected ? (
                <p
                  className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
                  role="alert"
                >
                  El monto recibido no cubre el total. Faltan{' '}
                  <span className="tabular font-semibold">
                    {currency === CURRENCY_VES
                      ? formatVes(expected - paid)
                      : formatUsd(expected - paid)}
                  </span>
                  . Para fiar la diferencia, elija «Fiada».
                </p>
              ) : null}
            </>
          )}

          <TextInput
            label="Notas"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Opcional"
          />

          <ErrorBanner error={createSale.error} />
        </div>
      )}
    </Sheet>
  )
}
