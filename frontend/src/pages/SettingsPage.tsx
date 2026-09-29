/** Settings: store configuration, BCV rate and the current session. */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '../components/ui/Button'
import { ErrorBanner, SuccessBanner } from '../components/ui/Feedback'
import { NumberInput, TextInput, Toggle } from '../components/ui/Field'
import { ListSkeleton } from '../components/ui/Skeleton'
import { Card } from '../components/ui/Primitives'
import { Sheet } from '../components/ui/Sheet'
import { useAuth } from '../hooks/useAuth'
import { useStoreConfig, useUpdateStoreConfig } from '../hooks/useCustomers'
import { useCurrentRate, useBcvSyncStatus, useRates, useRegisterManualRate, useSyncBcvRate } from '../hooks/useRates'
import { useCountdownMinutes, toMinutes } from '../hooks/useCountdown'
import { useDebts } from '../hooks/useDebts'
import { useGoodsEntries, useExitNotes, useStockMovements } from '../hooks/useInventory'
import { formatDate, formatDateTimeAmPm, toDateInput } from '../lib/date'
import { formatRate, formatUsd, parseMoney } from '../lib/money'
import { ROLE_LABELS } from '../lib/labels'
import type { StoreConfig } from '../types/api'

export function SettingsPage() {
  const { user, logout, hasRole } = useAuth()
  const navigate = useNavigate()
  const [isLogoutOpen, setIsLogoutOpen] = useState(false)

  const config = useStoreConfig()
  const rate = useCurrentRate()

  const canEditConfig = hasRole('ADMIN', 'GERENTE')
  const canEditRates = hasRole('ADMIN')

  return (
    <div className="space-y-4">
      <section>
        <h1 className="mb-2 text-lg font-semibold text-slate-900">Ajustes</h1>
        <Card className="p-3 text-sm">
          <p className="font-medium text-slate-800">{user?.full_name}</p>
          <p className="text-xs text-slate-500">@{user?.username}</p>
          <div className="mt-2 flex flex-wrap gap-1">
            {(user?.roles ?? []).map((role) => (
              <span
                key={role}
                className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
              >
                {ROLE_LABELS[role]}
              </span>
            ))}
          </div>
        </Card>
      </section>

      {canEditConfig && config.data ? (
        // `key` on the saved timestamp: the form starts from the stored values
        // and shows them again after a save, with no effect to reset it.
        <section aria-labelledby="config-heading">
          <h2 id="config-heading" className="mb-2 text-base font-semibold text-slate-900">
            Configuración de la tienda
          </h2>
          <ConfigForm key={config.data.updated_at} config={config.data} />
        </section>
      ) : null}

      {canEditRates ? (
        <section aria-labelledby="rate-heading">
          <h2 id="rate-heading" className="mb-2 text-base font-semibold text-slate-900">
            Tasa de cambio
          </h2>
          <RateSection />
        </section>
      ) : rate.data ? (
        <section>
          <h2 className="mb-2 text-base font-semibold text-slate-900">Tasa vigente</h2>
          <Card className="p-3 text-sm">
            <p className="tabular text-2xl font-bold text-slate-900">
              {formatRate(rate.data.rate)}
            </p>
            <p className="text-xs text-slate-500">
              {rate.data.source_display} · vigente {rate.data.effective_date}
            </p>
          </Card>
        </section>
      ) : null}

      <section aria-labelledby="inventory-heading">
        <h2 id="inventory-heading" className="mb-2 text-base font-semibold text-slate-900">
          Inventario
        </h2>
        <InventoryShortcuts />
      </section>

      <section>
        <Button
          variant="secondary"
          fullWidth
          onClick={() => setIsLogoutOpen(true)}
        >
          Cerrar sesión
        </Button>
      </section>

      <Sheet
        open={isLogoutOpen}
        onClose={() => setIsLogoutOpen(false)}
        title="Cerrar sesión"
        footer={
          <div className="flex gap-2">
            <Button variant="secondary" fullWidth onClick={() => setIsLogoutOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="danger"
              fullWidth
              onClick={async () => {
                await logout()
                navigate('/login', { replace: true })
              }}
            >
              Salir
            </Button>
          </div>
        }
      >
        <p className="text-sm text-slate-600">
          Se cerrará la sesión en este dispositivo y se descartarán los datos en caché.
        </p>
      </Sheet>
    </div>
  )
}

/** Store settings form. Mounted only once the configuration is loaded. */
function ConfigForm({ config }: { config: StoreConfig }) {
  const updateConfig = useUpdateStoreConfig()
  const [storeName, setStoreName] = useState(config.store_name)
  const [allowZeroStock, setAllowZeroStock] = useState(config.allow_zero_stock_sale)
  const [surcharge, setSurcharge] = useState(config.default_surcharge_percentage)
  const [saved, setSaved] = useState(false)

  async function onSave() {
    try {
      await updateConfig.mutate({
        store_name: storeName,
        allow_zero_stock_sale: allowZeroStock,
        default_surcharge_percentage: surcharge,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch {
      // Shown by the banner below.
    }
  }

  return (
    <Card className="space-y-3 p-3">
      <TextInput
        label="Nombre de la tienda"
        value={storeName}
        onChange={(event) => setStoreName(event.target.value)}
      />
      <Toggle
        label="Vender con existencia cero"
        description="Permite facturar artículos agotados. La diferencia queda como deuda de inventario y se cancela con la próxima entrada."
        checked={allowZeroStock}
        onChange={setAllowZeroStock}
      />
      <NumberInput
        label="Recargo por defecto (%)"
        hint="Se aplica al final de cada venta."
        value={surcharge}
        onChange={(event) => setSurcharge(event.target.value)}
        step="0.01"
      />
      {saved ? <SuccessBanner>Configuración guardada.</SuccessBanner> : null}
      <ErrorBanner error={updateConfig.error} />
      <Button fullWidth isLoading={updateConfig.isPending} onClick={onSave}>
        Guardar configuración
      </Button>
    </Card>
  )
}

function RateSection() {
  const rate = useCurrentRate()
  const rates = useRates({ pageSize: 10 })
  const syncStatus = useBcvSyncStatus()
  const sync = useSyncBcvRate()
  const manual = useRegisterManualRate()
  const [isManualOpen, setIsManualOpen] = useState(false)
  const minutesLeft = useCountdownMinutes(syncStatus.data?.next_sync_available_at)
  const isCoolingDown = minutesLeft !== null && minutesLeft > 0

  return (
    <>
      <Card className="space-y-3 p-3">
        {rate.isLoading ? (
          <ListSkeleton count={2} />
        ) : rate.isError ? (
          <ErrorBanner error={rate.error} />
        ) : rate.data ? (
          <div>
            <p className="tabular text-2xl font-bold text-slate-900">
              {formatRate(rate.data.rate)}
            </p>
            <p className="text-xs text-slate-500">
              {rate.data.source_display} · vigente {formatDate(rate.data.effective_date)}
            </p>
          </div>
        ) : null}

        <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
          <p>
            <span className="text-slate-500">Última consulta: </span>
            {syncStatus.isLoading ? (
              <span className="text-slate-400">cargando…</span>
            ) : (
              <span className="tabular font-medium text-slate-800">
                {formatDateTimeAmPm(syncStatus.data?.last_fetched_at)}
              </span>
            )}
          </p>
          <p className="mt-0.5">
            {isCoolingDown ? (
              <>
                <span className="text-slate-500">Próxima consulta disponible en </span>
                <span className="tabular font-semibold text-amber-700">{minutesLeft} min</span>
              </>
            ) : (
              <span className="font-medium text-emerald-700">
                Ya puedes consultar de nuevo.
              </span>
            )}
            {syncStatus.data && syncStatus.data.min_interval_seconds > 0 ? (
              <span className="text-slate-400">
                {' '}
                (intervalo de {toMinutes(syncStatus.data.min_interval_seconds)} min)
              </span>
            ) : null}
          </p>
        </div>

        <div className="flex gap-2">
          <Button
            variant="secondary"
            fullWidth
            isLoading={sync.isPending}
            // While the cooldown runs the request can only be rejected, so the
            // force button below takes its place instead of raising a 409.
            disabled={isCoolingDown}
            onClick={() => sync.mutate(undefined).catch(() => undefined)}
          >
            Sincronizar BCV
          </Button>
          <Button variant="secondary" fullWidth onClick={() => setIsManualOpen(true)}>
            Tasa manual
          </Button>
        </div>

        {isCoolingDown ? (
          <Button
            variant="ghost"
            fullWidth
            isLoading={sync.isPending}
            onClick={() => sync.mutate(true).catch(() => undefined)}
          >
            Forzar consulta ahora
          </Button>
        ) : null}

        <ErrorBanner error={sync.error ?? manual.error} />
      </Card>

      <Card className="mt-2">
        {rates.isLoading ? (
          <ListSkeleton count={4} />
        ) : rates.isError ? (
          <ErrorBanner error={rates.error} />
        ) : (
          <ul className="divide-y divide-slate-100 text-sm">
            {(rates.data?.results ?? []).map((item) => (
              <li key={item.id} className="flex items-center justify-between px-3 py-2">
                <div>
                  <p className="tabular font-medium">{formatRate(item.rate)}</p>
                  <p className="text-[11px] text-slate-500">
                    {item.source_display} · {formatDate(item.effective_date)}
                    {item.notes ? ` · ${item.notes}` : ''}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <ManualRateSheet open={isManualOpen} onClose={() => setIsManualOpen(false)} />
    </>
  )
}

function ManualRateSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const manual = useRegisterManualRate()
  const [rate, setRate] = useState('')
  const [date, setDate] = useState(() => toDateInput())
  const [notes, setNotes] = useState('')
  const [done, setDone] = useState(false)
  async function onSubmit() {
    try {
      await manual.mutate({ rate, effective_date: date, notes })
      setDone(true)
      setRate('')
      setNotes('')
    } catch {
      // Banner shows the reason.
    }
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Registrar tasa manual"
      footer={
        <Button
          fullWidth
          size="lg"
          isLoading={manual.isPending}
          disabled={!rate || notes.trim().length < 5}
          onClick={onSubmit}
        >
          Guardar tasa
        </Button>
      }
    >
      <div className="space-y-3">
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Úsela solo si falla la sincronización del BCV. No sobrescribe el historial oficial.
        </p>
        {done ? <SuccessBanner>Tasa manual registrada.</SuccessBanner> : null}
        <NumberInput
          label="Tasa (VES por 1 USD)"
          required
          value={rate}
          onChange={(event) => setRate(event.target.value)}
          step="0.0001"
        />
        <TextInput
          label="Fecha de vigencia"
          type="date"
          required
          value={date}
          onChange={(event) => setDate(event.target.value)}
        />
        <TextInput
          label="Motivo"
          required
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Mínimo 5 caracteres"
        />
        <ErrorBanner error={manual.error} />
      </div>
    </Sheet>
  )
}

function InventoryShortcuts() {
  const movements = useStockMovements({ pageSize: 5 })
  const entries = useGoodsEntries({ pageSize: 5 })
  const exitNotes = useExitNotes({ pageSize: 5 })
  const debts = useDebts({ openOnly: true, pageSize: 5 })

  return (
    <Card className="divide-y divide-slate-100 text-sm">
      <Counter label="Movimientos recientes" value={movements.data?.count} />
      <Counter label="Notas de entrada" value={entries.data?.count} />
      <Counter label="Notas de salida" value={exitNotes.data?.count} />
      <Counter
        label="Deudas abiertas"
        value={debts.data?.count}
        extra={
          debts.data
            ? formatUsd(
                debts.data.results.reduce((sum, debt) => sum + parseMoney(debt.balance_usd), 0),
              )
            : undefined
        }
      />
    </Card>
  )
}

function Counter({
  label,
  value,
  extra,
}: {
  label: string
  value: number | undefined
  extra?: string
}) {
  return (
    <div className="flex items-center justify-between px-3 py-2">
      <span className="text-slate-600">{label}</span>
      <span className="tabular font-medium">
        {value === undefined ? '—' : value}
        {extra ? <span className="ml-2 text-slate-500">{extra}</span> : null}
      </span>
    </div>
  )
}
