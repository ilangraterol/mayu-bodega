/** Sales: register a sale, quote a cart, list sales and read the till summary. */

import { useCallback } from 'react'

import { apiFetch } from '../lib/apiClient'
import { cacheKeys, endpoints } from '../lib/endpoints'
import { useApiQuery, type QueryResult } from '../lib/queryCache'
import { useMutation } from './useMutation'
import type {
  Paginated,
  Quote,
  Sale,
  SaleItemInput,
  SalePayload,
  SalesSummary,
} from '../types/api'

export interface SaleFilters {
  saleType?: string
  status?: string
  today?: boolean
  search?: string
  page?: number
  pageSize?: number
}

function buildPath(filters: SaleFilters): string {
  return endpoints.sales.list({
    sale_type: filters.saleType,
    status: filters.status,
    today: filters.today ? true : undefined,
    search: filters.search || undefined,
    page: filters.page,
    page_size: filters.pageSize,
    ordering: '-sale_date',
  })
}

export function useSales(filters: SaleFilters = {}): QueryResult<Paginated<Sale>> {
  return useApiQuery<Paginated<Sale>>(
    `${cacheKeys.sales}:${JSON.stringify(filters)}`,
    buildPath(filters),
    { staleTime: 10_000 },
  )
}

export function useSalesSummary(): QueryResult<SalesSummary> {
  return useApiQuery<SalesSummary>(cacheKeys.summary, endpoints.sales.summary, {
    staleTime: 20_000,
  })
}

/** Server-side totals: rate, surcharge and per-line availability come from BCV. */
export function useQuote() {
  const action = useCallback(
    (items: SaleItemInput[]) =>
      apiFetch<Quote>(endpoints.sales.quote, { method: 'POST', body: { items } }),
    [],
  )
  return useMutation(action)
}

export function useCreateSale() {
  const action = useCallback(
    (payload: SalePayload) => apiFetch<Sale>(endpoints.sales.list(), { method: 'POST', body: payload }),
    [],
  )
  return useMutation(action, {
    invalidates: [cacheKeys.sales, cacheKeys.summary, cacheKeys.products, cacheKeys.debts, cacheKeys.movements],
  })
}

export function useVoidSale() {
  const action = useCallback(
    (input: { id: number; reason: string }) =>
      apiFetch<Sale>(endpoints.sales.void(input.id), { method: 'POST', body: { reason: input.reason } }),
    [],
  )
  return useMutation(action, {
    invalidates: [cacheKeys.sales, cacheKeys.summary, cacheKeys.products, cacheKeys.debts, cacheKeys.movements],
  })
}
