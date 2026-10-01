/** App shell: sticky header, scrollable content and a bottom tab bar. */

import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { useCurrentRate } from '../../hooks/useRates'
import { useSalesSummary } from '../../hooks/useSales'
import { formatDayDateTime } from '../../lib/date'
import { formatNumber, formatUsd } from '../../lib/money'

const TABS = [
  { to: '/', label: 'Inicio', icon: '🏠', end: true },
  { to: '/vender', label: 'Vender', icon: '🛒', end: false },
  { to: '/productos', label: 'Productos', icon: '📦', end: false },
  { to: '/categorias', label: 'Categorías', icon: '🏷️', end: false },
  { to: '/creditos', label: 'Crédito', icon: '📒', end: false },
  { to: '/ajustes', label: 'Ajustes', icon: '⚙️', end: false },
]

export function AppLayout() {
  const { user, hasRole } = useAuth()
  const { data: rate } = useCurrentRate()
  // Shares the `sales-summary` cache key with the dashboard and the till, so
  // showing it here costs no extra request and it refreshes itself after a sale.
  const { data: summary } = useSalesSummary()

  return (
    <div className="flex min-h-dvh flex-col">
      {/* The content row is the fixed height; `pt-safe` sits above it, so the
          sticky bar on the till offsets by `--spacing-header-offset` (content
          plus inset) and cannot slip underneath. */}
      <header className="pt-safe sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        {/* Every line is `text-[11px]`: the header is dense on a phone and mixed
            font sizes made the two columns look unrelated. */}
        <div className="mx-auto flex h-header w-full max-w-3xl items-center justify-between gap-2 px-2">
          <div className="min-w-0">
            <p className="truncate text-[11px] font-medium text-slate-900">
              {user?.username ?? 'Mayu Bodega'}
            </p>
            {summary ? (
              <p className="tabular truncate text-[11px] text-slate-500">
                Hoy: {summary.sales_count} venta{summary.sales_count === 1 ? '' : 's'} por{' '}
                {formatUsd(summary.total_usd)}
              </p>
            ) : null}
          </div>
          {rate ? (
            <div className="shrink-0 rounded-lg bg-slate-100 px-2 py-1 text-right">
              {/* The rate keeps 2 decimals here so the label stays on one line;
                  `formatRate` (4 decimals) is preserved elsewhere for the legal
                  rate. `fetched_at` is when the BCV was last read, not the date
                  it published the value: a stale rate is visible at a glance. */}
              <p className="text-[11px] text-slate-600">Tasa BCV ({formatNumber(rate.rate, 2)})</p>
              <p className="text-[11px] text-slate-400">
                {formatDayDateTime(rate.fetched_at)}
              </p>
            </div>
          ) : (
            <span className="shrink-0 rounded-lg bg-amber-100 px-2 py-1 text-[10px] font-medium text-amber-900">
              Sin tasa
            </span>
          )}
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-3 pt-3 pb-24">
        <Outlet />
      </main>

      <nav
        className="pb-safe fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white"
        aria-label="Navegación principal"
      >
        <ul className="mx-auto flex w-full max-w-3xl items-stretch">
          {TABS.filter((tab) => {
            if (tab.to === '/vender') return hasRole('CAJERO', 'GERENTE')
            // Categories share the catalogue permissions.
            if (tab.to === '/productos' || tab.to === '/categorias') {
              return hasRole('ALMACENERO', 'GERENTE')
            }
            return true
          }).map((tab) => (
            <li key={tab.to} className="flex-1">
              <NavLink
                to={tab.to}
                end={tab.end}
                className={({ isActive }) =>
                  [
                    'flex min-h-14 flex-col items-center justify-center gap-0.5 text-[10px] font-medium',
                    isActive ? 'text-slate-900' : 'text-slate-400',
                  ].join(' ')
                }
              >
                {({ isActive }) => (
                  <>
                    <span className="text-lg leading-none" aria-hidden="true">
                      {tab.icon}
                    </span>
                    {tab.label}
                    {isActive ? (
                      <span className="absolute mt-0.5 h-0.5 w-6 rounded-full bg-slate-900" />
                    ) : null}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
