/** Exchange rates: current rate, history, BCV sync and the manual fallback. */

import { useCallback } from 'react'

import { apiFetch, toQuery } from '../lib/apiClient'
import { cacheKeys, endpoints } from '../lib/endpoints'
import { useApiQuery, type QueryResult } from '../lib/queryCache'
import { useMutation } from './useMutation'
import type { BcvSyncStatus, ExchangeRate, ManualRatePayload, Paginated } from '../types/api'

export function useCurrentRate(): QueryResult<ExchangeRate> {
  return useApiQuery<ExchangeRate>(`${cacheKeys.rates}:current`, endpoints.rates.current, {
    staleTime: 60_000,
  })
}

/**
 * When the BCV was last read and when the next one is allowed. Read once and
 * counted down locally, so it never becomes a source of extra requests.
 */
export function useBcvSyncStatus(): QueryResult<BcvSyncStatus> {
  return useApiQuery<BcvSyncStatus>(
    `${cacheKeys.rates}:sync-status`,
    endpoints.rates.syncStatus,
    { staleTime: 30_000 },
  )
}

export interface RateFilters {
  source?: string
  page?: number
  pageSize?: number
}

export function useRates(filters: RateFilters = {}): QueryResult<Paginated<ExchangeRate>> {
  return useApiQuery<Paginated<ExchangeRate>>(
    `${cacheKeys.rates}:list:${JSON.stringify(filters)}`,
    endpoints.rates.list({
      source: filters.source,
      page: filters.page,
      page_size: filters.pageSize,
      ordering: '-effective_date',
    }),
    { staleTime: 60_000 },
  )
}

/**
 * Pull the official rate from the BCV. The backend owns the parsing and the
 * cooldown; `force` ignores the cooldown and always performs one request.
 */
export function useSyncBcvRate() {
  const action = useCallback(
    (force?: boolean) =>
      apiFetch<ExchangeRate>(`${endpoints.rates.sync}${toQuery({ force })}`, { method: 'POST' }),
    [],
  )
  // `force` is optional so the caller can invoke `mutate()` with no argument.
  return useMutation<boolean | undefined, ExchangeRate>(action, { invalidates: [cacheKeys.rates] })
}

/** Administrator fallback: does not overwrite the official history. */
export function useRegisterManualRate() {
  const action = useCallback(
    (payload: ManualRatePayload) =>
      apiFetch<ExchangeRate>(endpoints.rates.manual, { method: 'POST', body: payload }),
    [],
  )
  return useMutation(action, { invalidates: [cacheKeys.rates] })
}
