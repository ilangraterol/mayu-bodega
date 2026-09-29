/** Shown while the session is being restored, to avoid a login flash. */

export function FullPageLoader() {
  return (
    <div className="flex min-h-dvh items-center justify-center" role="status" aria-label="Cargando">
      <div className="flex flex-col items-center gap-3">
        <span className="size-8 animate-spin rounded-full border-[3px] border-slate-300 border-t-slate-900" />
        <p className="text-sm text-slate-500">Cargando…</p>
      </div>
    </div>
  )
}
