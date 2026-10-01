/** Categories: the middle level of the surcharge chain (article > category > store). */

import { useCallback } from 'react'

import { apiFetch } from '../lib/apiClient'
import { cacheKeys, endpoints } from '../lib/endpoints'
import { useApiQuery, type QueryResult } from '../lib/queryCache'
import { useMutation } from './useMutation'
import type { Category, CategoryPayload, Paginated } from '../types/api'

export interface CategoryFilters {
  search?: string
  isActive?: boolean
  /** Inactive categories are hidden unless asked for, like the catalogue does. */
  includeInactive?: boolean
  page?: number
  pageSize?: number
}

function buildPath(filters: CategoryFilters): string {
  return endpoints.categories.list({
    search: filters.search || undefined,
    is_active: filters.isActive === undefined ? undefined : filters.isActive,
    include_inactive: filters.includeInactive ? true : undefined,
    page: filters.page,
    page_size: filters.pageSize,
    ordering: 'name',
  })
}

export function useCategories(
  filters: CategoryFilters = {},
): QueryResult<Paginated<Category>> {
  return useApiQuery<Paginated<Category>>(
    `${cacheKeys.categories}:${JSON.stringify(filters)}`,
    buildPath(filters),
    { staleTime: 60_000 },
  )
}

/** Categories as a flat, uncached-friendly list for selects in other screens. */
export function useCategoryOptions(): QueryResult<Paginated<Category>> {
  return useCategories({ includeInactive: false, pageSize: 100 })
}

export function useCreateCategory() {
  const action = useCallback(
    (payload: CategoryPayload) =>
      apiFetch<Category>(endpoints.categories.list(), { method: 'POST', body: payload }),
    [],
  )
  // Products cache their resolved surcharge, so a new category changes what the
  // till would charge: the catalogue cache has to go with it.
  return useMutation(action, { invalidates: [cacheKeys.categories, cacheKeys.products] })
}

export function useUpdateCategory(id: number) {
  const action = useCallback(
    (payload: Partial<CategoryPayload>) =>
      apiFetch<Category>(endpoints.categories.detail(id), { method: 'PATCH', body: payload }),
    [id],
  )
  return useMutation(action, { invalidates: [cacheKeys.categories, cacheKeys.products] })
}

/**
 * Deleting a category that still has articles is refused by the API, because the
 * foreign key protects them. The screen surfaces that message as-is.
 */
export function useDeleteCategory() {
  const action = useCallback(
    (id: number) => apiFetch<void>(endpoints.categories.detail(id), { method: 'DELETE' }),
    [],
  )
  return useMutation(action, { invalidates: [cacheKeys.categories, cacheKeys.products] })
}
