/**
 * Product photo manager.
 *
 * Uploads go as `multipart/form-data` so the browser supplies the boundary
 * (see `useUploadProductImage`). The backend re-encodes everything to WebP, caps
 * the long side and builds a small thumbnail, so this component only pre-checks
 * what the browser can check cheaply to save the user a round trip.
 *
 * Mobile-first: the grid is three fixed `aspect-square` tiles, so nothing shifts
 * while the WebP thumbnails stream in.
 */

import { useRef, useState } from 'react'

import { Button } from '../ui/Button'
import { ErrorBanner } from '../ui/Feedback'
import { toSameOrigin } from '../../lib/mediaUrl'
import { useDeleteProductImage, useSetPrimaryImage, useUploadProductImage } from '../../hooks/useProducts'
import type { Product } from '../../types/api'

/** Mirrors `catalog.image_processing` so obvious mistakes fail before upload. */
const MAX_BYTES = 10 * 1024 * 1024
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function ProductImages({ product }: { product: Product }) {
  const upload = useUploadProductImage(product.id)
  const setPrimary = useSetPrimaryImage()
  const removeImage = useDeleteProductImage()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [localError, setLocalError] = useState('')

  const images = product.images ?? []
  const isBusy = upload.isPending || setPrimary.isPending || removeImage.isPending

  async function onPick(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    // Reset first so picking the same file twice still fires a change event.
    event.target.value = ''
    if (!file) return

    if (!ACCEPTED_TYPES.includes(file.type)) {
      setLocalError('Formato no admitido. Usa JPEG, PNG, WebP o GIF.')
      return
    }
    if (file.size > MAX_BYTES) {
      setLocalError(`La foto pesa ${formatBytes(file.size)} y el máximo es 10 MB.`)
      return
    }

    setLocalError('')
    await upload.mutate(file).catch(() => undefined)
  }

  return (
    <section aria-labelledby="images-heading" className="space-y-2">
      <div className="flex items-baseline justify-between">
        <h3 id="images-heading" className="text-sm font-semibold text-slate-800">
          Fotos
        </h3>
        <span className="text-xs text-slate-500">
          {images.length === 0 ? 'Sin fotos' : `${images.length} foto${images.length === 1 ? '' : 's'}`}
        </span>
      </div>

      {images.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-3 py-4 text-center text-xs text-slate-500">
          Este artículo no tiene foto. En el punto de venta se verá un marcador con sus iniciales.
        </p>
      ) : (
        <ul className="grid grid-cols-3 gap-2">
          {images.map((image) => (
            <li key={image.id} className="relative">
              <img
                src={toSameOrigin(image.thumbnail_url)}
                alt={product.name}
                loading="lazy"
                decoding="async"
                width={image.width || undefined}
                height={image.height || undefined}
                className="aspect-square w-full rounded-lg border border-slate-200 bg-slate-100 object-cover"
              />
              {image.is_primary ? (
                <span className="absolute left-1 top-1 rounded-full bg-slate-900 px-1.5 py-0.5 text-[10px] font-medium text-white">
                  Principal
                </span>
              ) : null}
              <button
                type="button"
                disabled={isBusy}
                onClick={() => setPrimary.mutate(image.id).catch(() => undefined)}
                className="absolute inset-x-0 bottom-0 rounded-b-lg bg-white/90 py-1 text-[11px] font-medium text-slate-700 disabled:opacity-60"
              >
                {image.is_primary ? 'Principal' : 'Usar'}
              </button>
              <button
                type="button"
                aria-label={`Quitar foto de ${product.name}`}
                disabled={isBusy}
                onClick={() => removeImage.mutate(image.id).catch(() => undefined)}
                className="absolute right-1 top-1 flex size-6 items-center justify-center rounded-full bg-white/90 text-sm leading-none text-red-600 disabled:opacity-60"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(',')}
        onChange={onPick}
        className="sr-only"
        aria-label="Seleccionar foto del producto"
      />
      <Button
        type="button"
        variant="secondary"
        fullWidth
        isLoading={upload.isPending}
        onClick={() => inputRef.current?.click()}
      >
        {images.length === 0 ? 'Agregar foto' : 'Agregar otra foto'}
      </Button>

      <p className="text-xs text-slate-500">JPEG, PNG, WebP o GIF. Máximo 10 MB.</p>

      <ErrorBanner error={localError ? null : (upload.error ?? setPrimary.error ?? removeImage.error)} />
      {localError ? (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
          {localError}
        </p>
      ) : null}
    </section>
  )
}
