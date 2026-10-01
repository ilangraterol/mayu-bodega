/** Catalogue: product list, barcode lookup, detail, writes and image upload. */

import { useCallback } from 'react'

import { apiFetch } from '../lib/apiClient'
import { cacheKeys, endpoints } from '../lib/endpoints'
import { useApiQuery, type QueryResult } from '../lib/queryCache'
import { useMutation } from './useMutation'
import type { Paginated, Product, ProductPayload } from '../types/api'

export interface ProductFilters {
  search?: string
  /** The API hides inactive products unless `include_inactive` is true. */
  includeInactive?: boolean
  lowStock?: boolean
  outOfStock?: boolean
  /** Category id; the API filters on the exact category, not its children. */
  category?: number | null
  page?: number
  pageSize?: number
}

function buildPath(filters: ProductFilters): string {
  return endpoints.products.list({
    search: filters.search || undefined,
    include_inactive: filters.includeInactive ? true : undefined,
    low_stock: filters.lowStock ? true : undefined,
    out_of_stock: filters.outOfStock ? true : undefined,
    category: filters.category ?? undefined,
    page: filters.page,
    page_size: filters.pageSize,
    ordering: 'name',
  })
}

function buildKey(filters: ProductFilters): string {
  return `${cacheKeys.products}:${JSON.stringify(filters)}`
}

export function useProducts(filters: ProductFilters = {}): QueryResult<Paginated<Product>> {
  return useApiQuery<Paginated<Product>>(buildKey(filters), buildPath(filters), {
    staleTime: 15_000,
  })
}

export function useProduct(id: number | null): QueryResult<Product> {
  return useApiQuery<Product>(
    id === null ? null : `${cacheKeys.products}:detail:${id}`,
    endpoints.products.detail(id ?? 0),
    { staleTime: 15_000 },
  )
}

export function useCreateProduct() {
  const action = useCallback(
    (payload: ProductPayload) =>
      apiFetch<Product>(endpoints.products.list(), { method: 'POST', body: payload }),
    [],
  )
  return useMutation(action, { invalidates: [cacheKeys.products, cacheKeys.movements] })
}

export function useUpdateProduct(id: number) {
  const action = useCallback(
    (payload: Partial<ProductPayload>) =>
      apiFetch<Product>(endpoints.products.detail(id), { method: 'PATCH', body: payload }),
    [id],
  )
  return useMutation(action, { invalidates: [cacheKeys.products] })
}

/**
 * Upload an image as multipart/form-data so the browser supplies the boundary.
 */
export function useUploadProductImage(productId: number) {
  const action = useCallback(
    (file: File) => {
      const formData = new FormData()
      formData.append('product', String(productId))
      formData.append('image', file)
      return apiFetch<unknown>(endpoints.productImages.upload, { method: 'POST', formData })
    },
    [productId],
  )
  return useMutation(action, { invalidates: [cacheKeys.products, cacheKeys.productImages] })
}

export function useSetPrimaryImage() {
  const action = useCallback(
    (imageId: number) =>
      apiFetch<unknown>(endpoints.productImages.setPrimary(imageId), { method: 'POST' }),
    [],
  )
  return useMutation(action, { invalidates: [cacheKeys.products, cacheKeys.productImages] })
}
export function useDeleteProductImage() {
  const action = useCallback(
    (imageId: number) =>
      apiFetch<void>(endpoints.productImages.detail(imageId), { method: 'DELETE' }),
    [],
  )
  return useMutation(action, { invalidates: [cacheKeys.products, cacheKeys.productImages] })
}
