/** Inventory: stock ledger, goods entries and exit notes. */

import { useCallback } from 'react'

import { apiFetch } from '../lib/apiClient'
import { cacheKeys, endpoints } from '../lib/endpoints'
import { useApiQuery, type QueryResult } from '../lib/queryCache'
import { useMutation } from './useMutation'
import type {
  ExitNote,
  ExitNotePayload,
  GoodsEntry,
  GoodsEntryPayload,
  Paginated,
  StockMovement,
} from '../types/api'

export interface MovementFilters {
  productId?: number
  movementType?: string
  origin?: string
  search?: string
  page?: number
  pageSize?: number
}

function buildMovementPath(filters: MovementFilters): string {
  return endpoints.movements.list({
    product_id: filters.productId,
    movement_type: filters.movementType,
    origin: filters.origin,
    search: filters.search || undefined,
    page: filters.page,
    page_size: filters.pageSize,
    ordering: '-occurred_at',
  })
}

export function useStockMovements(
  filters: MovementFilters = {},
): QueryResult<Paginated<StockMovement>> {
  return useApiQuery<Paginated<StockMovement>>(
    `${cacheKeys.movements}:${JSON.stringify(filters)}`,
    buildMovementPath(filters),
    { staleTime: 10_000 },
  )
}

export interface EntryFilters {
  isCancelled?: boolean
  currency?: string
  search?: string
  page?: number
  pageSize?: number
}

export function useGoodsEntries(
  filters: EntryFilters = {},
): QueryResult<Paginated<GoodsEntry>> {
  return useApiQuery<Paginated<GoodsEntry>>(
    `${cacheKeys.entries}:${JSON.stringify(filters)}`,
    endpoints.goodsEntries.list({
      is_cancelled: filters.isCancelled === undefined ? undefined : filters.isCancelled,
      currency: filters.currency,
      search: filters.search || undefined,
      page: filters.page,
      page_size: filters.pageSize,
      ordering: '-entry_date',
    }),
    { staleTime: 15_000 },
  )
}

export function useCreateGoodsEntry() {
  const action = useCallback(
    (payload: GoodsEntryPayload) =>
      apiFetch<GoodsEntry>(endpoints.goodsEntries.list(), { method: 'POST', body: payload }),
    [],
  )
  return useMutation(action, {
    invalidates: [cacheKeys.entries, cacheKeys.products, cacheKeys.movements],
  })
}

export function useCancelGoodsEntry() {
  const action = useCallback(
    (input: { id: number; reason: string }) =>
      apiFetch<GoodsEntry>(endpoints.goodsEntries.cancel(input.id), {
        method: 'POST',
        body: { reason: input.reason },
      }),
    [],
  )
  return useMutation(action, {
    invalidates: [cacheKeys.entries, cacheKeys.products, cacheKeys.movements],
  })
}

export interface ExitNoteFilters {
  isCancelled?: boolean
  reason?: string
  page?: number
  pageSize?: number
}

export function useExitNotes(
  filters: ExitNoteFilters = {},
): QueryResult<Paginated<ExitNote>> {
  return useApiQuery<Paginated<ExitNote>>(
    `${cacheKeys.exitNotes}:${JSON.stringify(filters)}`,
    endpoints.exitNotes.list({
      is_cancelled: filters.isCancelled === undefined ? undefined : filters.isCancelled,
      reason: filters.reason,
      page: filters.page,
      page_size: filters.pageSize,
      ordering: '-exit_date',
    }),
    { staleTime: 15_000 },
  )
}

export function useCreateExitNote() {
  const action = useCallback(
    (payload: ExitNotePayload) =>
      apiFetch<ExitNote>(endpoints.exitNotes.list(), { method: 'POST', body: payload }),
    [],
  )
  return useMutation(action, {
    invalidates: [cacheKeys.exitNotes, cacheKeys.products, cacheKeys.movements],
  })
}

export function useCancelExitNote() {
  const action = useCallback(
    (input: { id: number; reason: string }) =>
      apiFetch<ExitNote>(endpoints.exitNotes.cancel(input.id), {
        method: 'POST',
        body: { reason: input.reason },
      }),
    [],
  )
  return useMutation(action, {
    invalidates: [cacheKeys.exitNotes, cacheKeys.products, cacheKeys.movements],
  })
}
