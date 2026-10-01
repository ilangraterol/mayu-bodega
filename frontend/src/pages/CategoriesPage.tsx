/**
 * Category management: the middle tier of the surcharge chain.
 *
 * A category may leave its percentage empty, which means "inherit" and lets the
 * store default apply. `Heredado` is shown as such so nobody reads a blank
 * percentage as zero.
 */

import { useState } from 'react'

import { Button } from '../components/ui/Button'
import { EmptyState, ErrorBanner, ErrorState } from '../components/ui/Feedback'
import { NumberInput, TextInput, Toggle } from '../components/ui/Field'
import { ListSkeleton } from '../components/ui/Skeleton'
import { Badge, Card } from '../components/ui/Primitives'
import { Sheet } from '../components/ui/Sheet'
import {
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useUpdateCategory,
} from '../hooks/useCategories'
import { formatPercent } from '../lib/money'
import type { Category, CategoryPayload } from '../types/api'

export function CategoriesPage() {
  const [search, setSearch] = useState('')
  const [editing, setEditing] = useState<number | 'new' | null>(null)

  const categories = useCategories({ search: search.trim() || undefined, pageSize: 100 })

  return (
    <div className="space-y-3">
      <TextInput
        label="Buscar categoría"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Nombre o código"
        autoCapitalize="none"
      />

      <Button fullWidth onClick={() => setEditing('new')}>
        Nueva categoría
      </Button>

      {categories.isLoading ? (
        <Card>
          <ListSkeleton count={6} />
        </Card>
      ) : categories.isError ? (
        <Card>
          <ErrorState
            error={categories.error}
            onRetry={categories.refetch}
            title="No pudimos cargar las categorías"
          />
        </Card>
      ) : (categories.data?.results.length ?? 0) === 0 ? (
        <Card>
          <EmptyState
            icon="🏷️"
            title={search ? 'Sin coincidencias' : 'Sin categorías'}
            description={
              search
                ? `Ninguna categoría coincide con «${search}».`
                : 'Agrupa artículos para aplicarles un recargo común.'
            }
          />
        </Card>
      ) : (
        <Card>
          <ul className="divide-y divide-slate-100">
            {categories.data!.results.map((category) => (
              <li key={category.id} className="flex items-center gap-2 p-2.5">
                <button
                  type="button"
                  onClick={() => setEditing(category.id)}
                  className="min-w-0 flex-1 text-left"
                >
                  <p className="truncate text-sm font-medium text-slate-800">{category.name}</p>
                  <p className="tabular truncate text-xs text-slate-500">
                    {category.code} · {category.product_count} art.
                  </p>
                </button>
                {category.surcharge_percentage === null ? (
                  <Badge tone="neutral">heredado</Badge>
                ) : (
                  <Badge tone="info">+{formatPercent(category.surcharge_percentage)}</Badge>
                )}
                {!category.is_active ? <Badge tone="warning">inactiva</Badge> : null}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <CategorySheet
        target={editing}
        onClose={() => setEditing(null)}
        onSaved={() => setEditing(null)}
      />
    </div>
  )
}

function CategorySheet({
  target,
  onClose,
  onSaved,
}: {
  target: number | 'new' | null
  onClose: () => void
  onSaved: () => void
}) {
  const categories = useCategories()
  const current =
    target !== 'new' ? categories.data?.results.find((item) => item.id === target) : undefined

  return (
    <Sheet
      open={target !== null}
      onClose={onClose}
      title={target === 'new' ? 'Nueva categoría' : (current?.name ?? 'Categoría')}
    >
      {target !== 'new' && !current && categories.isLoading ? (
        <ListSkeleton count={4} />
      ) : (
        // `key` remounts the form per category, so the fields start from the
        // loaded record and no previous error survives the switch.
        <CategoryForm
          key={target === 'new' ? 'new' : String(target)}
          category={current}
          onSaved={onSaved}
        />
      )}
    </Sheet>
  )
}

function CategoryForm({
  category,
  onSaved,
}: {
  category: Category | undefined
  onSaved: () => void
}) {
  const create = useCreateCategory()
  const update = useUpdateCategory(category?.id ?? 0)
  // One mutation object drives both paths, so the button state and the error
  // banner behave the same whether the record is new or existing.
  const mutation = category ? update : create
  const [form, setForm] = useState<CategoryPayload>(() => toForm(category))
  const [confirmedDeletion, setConfirmedDeletion] = useState(false)
  const remove = useDeleteCategory()

  async function onSave() {
    const payload: CategoryPayload = {
      ...form,
      // Empty means "inherit", which the API stores as null.
      surcharge_percentage: form.surcharge_percentage === '' ? null : form.surcharge_percentage,
    }
    try {
      if (category) await update.mutate(payload)
      else await create.mutate(payload)
      onSaved()
    } catch {
      // The banner below shows the failure.
    }
  }

  async function onDelete() {
    if (!category) return
    try {
      await remove.mutate(category.id)
      onSaved()
    } catch {
      setConfirmedDeletion(false)
    }
  }

  return (
    <>
      <div className="space-y-3">
        {category ? (
          <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
            <p>
              Código: <span className="tabular font-medium">{category.code}</span>
            </p>
            <p className="mt-1">
              Artículos: <span className="tabular font-medium">{category.product_count}</span>
              {category.product_count > 0
                ? ' · hay que reasignarlos antes de eliminar'
                : ''}
            </p>
          </div>
        ) : null}

        <TextInput
          label="Nombre"
          required
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
          placeholder="Bebidas, Limpieza, Abarrotes…"
        />
        <NumberInput
          label="Recargo (%)"
          hint="Vacío = hereda el valor de la tienda. Entre 0 y 100."
          min="0"
          max="100"
          step="0.01"
          value={form.surcharge_percentage ?? ''}
          onChange={(event) => setForm({ ...form, surcharge_percentage: event.target.value })}
        />
        <Toggle
          label="Categoría activa"
          description="Las inactivas no se ofrecen al elegir el recargo de un artículo."
          checked={form.is_active ?? true}
          onChange={(checked) => setForm({ ...form, is_active: checked })}
        />

        <ErrorBanner error={mutation.error ?? remove.error} />
      </div>

      <div className="mt-4 space-y-2">
        <Button
          fullWidth
          size="lg"
          isLoading={mutation.isPending}
          disabled={!form.name.trim()}
          onClick={onSave}
        >
          {category ? 'Guardar cambios' : 'Crear categoría'}
        </Button>

        {category ? (
          category.product_count > 0 ? null : confirmedDeletion ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm">
              <p className="text-red-800">
                «{category.name}» se eliminará. Esta acción no se puede deshacer.
              </p>
              <div className="mt-2 flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  fullWidth
                  onClick={() => setConfirmedDeletion(false)}
                >
                  Cancelar
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  fullWidth
                  isLoading={remove.isPending}
                  onClick={onDelete}
                >
                  Eliminar
                </Button>
              </div>
            </div>
          ) : (
            <Button variant="danger" fullWidth onClick={() => setConfirmedDeletion(true)}>
              Eliminar categoría
            </Button>
          )
        ) : null}
      </div>
    </>
  )
}

function toForm(category: Category | undefined): CategoryPayload {
  return {
    name: category?.name ?? '',
    surcharge_percentage: category?.surcharge_percentage ?? '',
    is_active: category?.is_active ?? true,
  }
}
