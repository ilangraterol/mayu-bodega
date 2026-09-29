/** App shell: sticky header, scrollable content and a bottom tab bar. */

import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../../hooks/useAuth'
import { useCurrentRate } from '../../hooks/useRates'
import { formatRate } from '../../lib/money'
import { ROLE_LABELS } from '../../lib/labels'

const TABS = [
  { to: '/', label: 'Inicio', icon: '🏠', end: true },
  { to: '/vender', label: 'Vender', icon: '🛒', end: false },
  { to: '/productos', label: 'Productos', icon: '📦', end: false },
  { to: '/creditos', label: 'Crédito', icon: '📒', end: false },
  { to: '/ajustes', label: 'Ajustes', icon: '⚙️', end: false },
]

export function AppLayout() {
  const { user, hasRole } = useAuth()
  const { data: rate } = useCurrentRate()

  const role = user?.roles?.[0]
  const roleLabel = role ? (ROLE_LABELS[role] ?? role) : ''

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="pt-safe sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 px-3 py-2.5">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-900">
              {user?.full_name ?? 'Mayu Bodega'}
            </p>
            <p className="truncate text-[11px] text-slate-500">{roleLabel}</p>
          </div>
          {rate ? (
            <div className="shrink-0 rounded-lg bg-slate-100 px-2 py-1 text-right">
              <p className="text-[10px] text-slate-500">Tasa BCV</p>
              <p className="tabular text-xs font-semibold text-slate-800">
                {formatRate(rate.rate)}
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
            if (tab.to === '/productos') return hasRole('ALMACENERO', 'GERENTE')
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
