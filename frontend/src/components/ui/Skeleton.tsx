/** Loading skeletons. Fixed dimensions avoid layout shift while images load. */

interface SkeletonProps {
  className?: string
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return <div className={`skeleton rounded-lg ${className}`} aria-hidden="true" />
}

/** Product card placeholder: image block plus two text lines. */
export function ProductCardSkeleton() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-2">
      <Skeleton className="aspect-square w-full" />
      <Skeleton className="mt-2 h-3 w-4/5" />
      <Skeleton className="mt-1.5 h-4 w-1/2" />
    </div>
  )
}

export function ProductGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <div
      className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4"
      role="status"
      aria-label="Cargando productos"
    >
      {Array.from({ length: count }, (_, index) => (
        <ProductCardSkeleton key={index} />
      ))}
    </div>
  )
}

export function ListRowSkeleton() {
  return (
    <div className="flex items-center gap-3 border-b border-slate-100 px-3 py-3">
      <Skeleton className="h-11 w-11 shrink-0 rounded-lg" />
      <div className="flex-1 space-y-1.5">
        <Skeleton className="h-3.5 w-3/5" />
        <Skeleton className="h-3 w-2/5" />
      </div>
      <Skeleton className="h-4 w-16" />
    </div>
  )
}

export function ListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="divide-y divide-slate-100" role="status" aria-label="Cargando">
      {Array.from({ length: count }, (_, index) => (
        <ListRowSkeleton key={index} />
      ))}
    </div>
  )
}

export function StatCardSkeleton() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <Skeleton className="h-3 w-1/2" />
      <Skeleton className="mt-2 h-6 w-3/4" />
    </div>
  )
}
