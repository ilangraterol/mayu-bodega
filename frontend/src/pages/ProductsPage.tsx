import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { ProductImage } from '../components/products/ProductImage'
import { ProductImages } from '../components/products/ProductImages'
import { Button } from '../components/ui/Button'
import { EmptyState, ErrorState } from '../components/ui/Feedback'
import { TextInput } from '../components/ui/Field'
import { ListSkeleton } from '../components/ui/Skeleton'
import { Badge, Card } from '../components/ui/Primitives'
import { Sheet } from '../components/ui/Sheet'
import { useProduct, useProducts, useUpdateProduct } from '../hooks/useProducts'
import { NumberInput, Select, TextInput as Input, Toggle } from '../components/ui/Field'
import { UNIT_OPTIONS, UNIT_LABELS } from '../lib/labels'
import { formatQuantity, formatUsd } from '../lib/money'
import type { Product, ProductPayload, UnitOfMeasure } from '../types/api'

export function ProductsPage() {
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [lowOnly, setLowOnly] = useState(params.get('low') === '1')
  const [editing, setEditing] = useState<number | null>(null)

  const products = useProducts({
    search: search.trim() || undefined,
    lowStock: lowOnly,
    pageSize: 50,
  })

  // The URL keeps the "stock bajo" filter shareable, so the dashboard can link
  // straight to it. It is written from the toggle handler, not from an effect.
  function showOnlyLow(next: boolean) {
    setLowOnly(next)
    setParams(next ? { low: '1' } : {}, { replace: true })
  }


  return (
    <div className="space-y-3">
      <TextInput
        label="Buscar producto"
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Nombre, marca, código o código de barras"
        autoCapitalize="none"
      />

      <div className="flex gap-1.5">
        <button
          type="button"
          onClick={() => showOnlyLow(false)}
          className={`rounded-full px-3 py-1.5 text-xs font-medium ${
            !lowOnly ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white text-slate-600'
          }`}
        >
          Todos
        </button>
        <button
          type="button"
          onClick={() => showOnlyLow(true)}
          className={`rounded-full px-3 py-1.5 text-xs font-medium ${
            lowOnly ? 'bg-slate-900 text-white' : 'border border-slate-300 bg-white text-slate-600'
          }`}
        >
          Stock bajo
        </button>
      </div>

      {products.isLoading ? (
        <Card>
          <ListSkeleton count={8} />
        </Card>
      ) : products.isError ? (
        <Card>
          <ErrorState error={products.error} onRetry={products.refetch} />
        </Card>
      ) : (products.data?.results.length ?? 0) === 0 ? (
        <Card>
          <EmptyState
            icon="📦"
            title={lowOnly ? 'Nada con stock bajo' : 'Catálogo vacío'}
            description={
              lowOnly
                ? 'Todos los productos están por encima de su empaque.'
                : 'Registra productos desde el panel de administración.'
            }
          />
        </Card>
      ) : (
        <>
          <p className="text-xs text-slate-500">
            {products.data!.count} producto{products.data!.count === 1 ? '' : 's'}
          </p>
          <Card>
            <ul className="divide-y divide-slate-100">
              {products.data!.results.map((product) => (
                <li key={product.id}>
                  <button
                    type="button"
                    onClick={() => setEditing(product.id)}
                    className="flex w-full items-center gap-3 p-2.5 text-left"
                  >
                    <div className="size-12 shrink-0 overflow-hidden rounded-lg">
                      <ProductImage src={product.primary_image_url} alt={product.name} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-800">
                        {product.name}
                      </p>
                      <p className="tabular truncate text-xs text-slate-500">
                        {product.code} · {formatUsd(product.price_usd)} ·{' '}
                        {UNIT_LABELS[product.unit_of_measure]}
                      </p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="tabular text-sm font-semibold text-slate-900">
                        {formatQuantity(product.stock)}
                      </p>
                      {Number.parseFloat(product.pending_units) > 0 ? (
                        <Badge tone="danger">debe {formatQuantity(product.pending_units)}</Badge>
                      ) : null}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </>
      )}

      <ProductSheet id={editing} onClose={() => setEditing(null)} />
    </div>
  )
}

function ProductSheet({ id, onClose }: { id: number | null; onClose: () => void }) {
  const product = useProduct(id)

  return (
    <Sheet
      open={id !== null}
      onClose={onClose}
      title={product.data ? product.data.name : 'Producto'}
    >
      {product.isLoading ? (
        <ListSkeleton count={4} />
      ) : product.isError ? (
        <ErrorState error={product.error} onRetry={product.refetch} />
      ) : product.data ? (
        // `key` remounts the form per product, so its state starts from the
        // loaded record and the mutation starts without a previous error.
        <ProductForm key={product.data.id} product={product.data} />
      ) : null}
    </Sheet>
  )
}

function toForm(product: Product): ProductPayload {
  return {
    name: product.name,
    barcode: product.barcode,
    brand: product.brand,
    unit_of_measure: product.unit_of_measure,
    units_per_package: product.units_per_package,
    cost_usd: product.cost_usd,
    price_usd: product.price_usd,
    is_active: product.is_active,
    notes: product.notes,
  }
}

function ProductForm({ product }: { product: Product }) {
  const update = useUpdateProduct(product.id)
  // Initialized directly from the record: no effect, no cascading render.
  const [form, setForm] = useState<ProductPayload>(() => toForm(product))

  async function onSave() {
    await update.mutate(form).catch(() => undefined)
  }

  return (
    <>
      <div className="space-y-3">
        <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
          <p>
            Código: <span className="tabular font-medium">{product.code}</span>
          </p>
          <p className="mt-1">
            Existencias:{' '}
            <span className="tabular font-medium">{formatQuantity(product.stock)}</span>
            {Number.parseFloat(product.pending_units) > 0 ? (
              <span className="text-red-600">
                {' '}
                · debe {formatQuantity(product.pending_units)}
              </span>
            ) : null}
          </p>
          <p className="mt-1 text-slate-500">
            El stock solo cambia por notas de entrada, salidas y ventas.
          </p>
        </div>

        <Input
          label="Nombre del artículo"
          required
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
        />
        <Input
          label="Código de barras"
          value={form.barcode ?? ''}
          onChange={(event) => setForm({ ...form, barcode: event.target.value || null })}
          autoCapitalize="none"
        />
        <Input
          label="Marca"
          value={form.brand}
          onChange={(event) => setForm({ ...form, brand: event.target.value })}
        />
        <Select
          label="Unidad de medida"
          value={form.unit_of_measure}
          onChange={(event) =>
            setForm({ ...form, unit_of_measure: event.target.value as UnitOfMeasure })
          }
          options={UNIT_OPTIONS}
        />
        <NumberInput
          label="Unidades por empaque"
          hint="Equivalencia interna de un bulto o paquete."
          value={String(form.units_per_package ?? 1)}
          onChange={(event) =>
            setForm({ ...form, units_per_package: Number(event.target.value) || 1 })
          }
          step="1"
        />
        <div className="grid grid-cols-2 gap-3">
          <NumberInput
            label="Costo (USD)"
            value={form.cost_usd}
            onChange={(event) => setForm({ ...form, cost_usd: event.target.value })}
          />
          <NumberInput
            label="Precio (USD)"
            value={form.price_usd}
            onChange={(event) => setForm({ ...form, price_usd: event.target.value })}
          />
        </div>
        <Toggle
          label="Producto activo"
          description="Los inactivos no aparecen en el punto de venta."
          checked={form.is_active ?? true}
          onChange={(checked) => setForm({ ...form, is_active: checked })}
        />

        <div className="border-t border-slate-100 pt-3">
          <ProductImages product={product} />
        </div>

        {update.isPending ? null : update.error ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            {update.error.detail}
          </p>
        ) : null}
      </div>

      <div className="mt-4">
        <Button
          fullWidth
          size="lg"
          isLoading={update.isPending}
          disabled={!form.name.trim()}
          onClick={onSave}
        >
          Guardar cambios
        </Button>
      </div>
    </>
  )
}
