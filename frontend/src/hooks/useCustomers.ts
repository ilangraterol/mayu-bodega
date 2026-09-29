/** Customers and the store configuration singleton. */

import { useCallback } from 'react'

import { apiFetch } from '../lib/apiClient'
import { cacheKeys, endpoints } from '../lib/endpoints'
import { useApiQuery, type QueryResult } from '../lib/queryCache'
import { useMutation } from './useMutation'
import type {
  Customer,
  CustomerPayload,
  CustomerStatement,
  Paginated,
  StoreConfig,
} from '../types/api'

export interface CustomerFilters {
  search?: string
  isActive?: boolean
  withBalance?: boolean
  page?: number
  pageSize?: number
}

function buildPath(filters: CustomerFilters): string {
  return endpoints.customers.list({
    search: filters.search || undefined,
    is_active: filters.isActive === undefined ? undefined : filters.isActive,
    with_balance: filters.withBalance ? true : undefined,
    page: filters.page,
    page_size: filters.pageSize,
    ordering: filters.withBalance ? undefined : 'name',
  })
}

export function useCustomers(filters: CustomerFilters = {}): QueryResult<Paginated<Customer>> {
  return useApiQuery<Paginated<Customer>>(
    `${cacheKeys.customers}:${JSON.stringify(filters)}`,
    buildPath(filters),
    { staleTime: 60_000 },
  )
}

export function useCustomerStatement(id: number | null): QueryResult<CustomerStatement> {
  return useApiQuery<CustomerStatement>(
    id === null ? null : `${cacheKeys.customers}:statement:${id}`,
    endpoints.customers.statement(id ?? 0),
    { staleTime: 10_000 },
  )
}

export function useCreateCustomer() {
  const action = useCallback(
    (payload: CustomerPayload) =>
      apiFetch<Customer>(endpoints.customers.list(), { method: 'POST', body: payload }),
    [],
  )
  return useMutation(action, { invalidates: [cacheKeys.customers] })
}

export function useUpdateCustomer(id: number) {
  const action = useCallback(
    (payload: Partial<CustomerPayload>) =>
      apiFetch<Customer>(endpoints.customers.detail(id), { method: 'PATCH', body: payload }),
    [id],
  )
  return useMutation(action, { invalidates: [cacheKeys.customers] })
}

export function useStoreConfig(): QueryResult<StoreConfig> {
  return useApiQuery<StoreConfig>(cacheKeys.config, endpoints.storeConfig.list, {
    staleTime: 120_000,
  })
}

export function useUpdateStoreConfig() {
  const action = useCallback(
    (payload: Partial<StoreConfig>) =>
      apiFetch<StoreConfig>(endpoints.storeConfig.detail(), { method: 'PATCH', body: payload }),
    [],
  )
  return useMutation(action, { invalidates: [cacheKeys.config, cacheKeys.products] })
}
