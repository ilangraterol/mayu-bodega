/** Empty and error states. Both are descriptive, never a bare "no data". */

import type { ReactNode } from 'react'

import type { ApiError } from '../../lib/apiClient'

interface EmptyStateProps {
  title: string
  description: string
  icon?: ReactNode
  action?: ReactNode
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-2xl">
        {icon ?? '📦'}
      </div>
      <h3 className="text-base font-semibold text-slate-800">{title}</h3>
      <p className="max-w-xs text-sm text-slate-500">{description}</p>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  )
}

interface ErrorStateProps {
  error: ApiError | null
  onRetry?: () => void
  /** Overrides the default heading, e.g. "No pudimos cargar los productos". */
  title?: string
}

function titleFor(error: ApiError | null): string {
  if (!error) return 'Algo salió mal'
  if (error.isUnauthorized) return 'Sesión expirada'
  if (error.status === 0) return 'Sin conexión'
  if (error.status === 404) return 'No encontrado'
  if (error.status >= 500) return 'Error del servidor'
  return 'No se pudo completar la operación'
}

export function ErrorState({ error, onRetry, title }: ErrorStateProps) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center"
      role="alert"
      aria-live="assertive"
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-2xl">
        ⚠️
      </div>
      <h3 className="text-base font-semibold text-slate-800">{title ?? titleFor(error)}</h3>
      <p className="max-w-xs text-sm text-slate-600">{error?.detail ?? 'Intente de nuevo.'}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white active:scale-95"
        >
          Reintentar
        </button>
      ) : null}
    </div>
  )
}

/** Slim inline banner for field-level or action-level failures. */
export function ErrorBanner({ error }: { error: ApiError | null }) {
  if (!error) return null
  const fields = Object.entries(error.fieldErrors)
  return (
    <div
      className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
      role="alert"
    >
      <p className="font-medium">{error.detail ?? 'Revise los datos e intente de nuevo.'}</p>
      {fields.length > 0 ? (
        <ul className="mt-1 list-inside list-disc space-y-0.5">
          {fields.map(([field, messages]) => (
            <li key={field}>
              <span className="font-semibold">{field}:</span> {messages.join(' ')}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}

export function SuccessBanner({ children }: { children: ReactNode }) {
  return (
    <div
      className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
      role="status"
      aria-live="polite"
    >
      {children}
    </div>
  )
}
