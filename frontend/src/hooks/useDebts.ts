/** Customer credit: open debts, payments (abonos) and payment reversals. */

import { useCallback } from 'react'

import { apiFetch } from '../lib/apiClient'
import { cacheKeys, endpoints } from '../lib/endpoints'
import { useApiQuery, type QueryResult } from '../lib/queryCache'
import { useMutation } from './useMutation'
import type {
  CustomerDebt,
  DebtPayment,
  DebtPaymentCreated,
  DebtPaymentPayload,
  Paginated,
} from '../types/api'

export interface DebtFilters {
  status?: string
  customer?: number
  openOnly?: boolean
  search?: string
  page?: number
  pageSize?: number
}

function buildPath(filters: DebtFilters): string {
  return endpoints.debts.list({
    status: filters.status,
    customer: filters.customer,
    open_only: filters.openOnly ? true : undefined,
    search: filters.search || undefined,
    page: filters.page,
    page_size: filters.pageSize,
    ordering: '-created_at',
  })
}

export function useDebts(filters: DebtFilters = {}): QueryResult<Paginated<CustomerDebt>> {
  return useApiQuery<Paginated<CustomerDebt>>(
    `${cacheKeys.debts}:${JSON.stringify(filters)}`,
    buildPath(filters),
    { staleTime: 10_000 },
  )
}

export function useDebt(id: number | null): QueryResult<CustomerDebt> {
  return useApiQuery<CustomerDebt>(
    id === null ? null : `${cacheKeys.debts}:detail:${id}`,
    endpoints.debts.detail(id ?? 0),
    { staleTime: 5_000 },
  )
}

export function useDebtPayments(debtId: number | null): QueryResult<Paginated<DebtPayment>> {
  return useApiQuery<Paginated<DebtPayment>>(
    debtId === null ? null : `${cacheKeys.payments}:${debtId}`,
    endpoints.debtPayments.list({ debt: debtId ?? 0, ordering: '-paid_at' }),
    { staleTime: 5_000 },
  )
}

/** The response carries the payment plus the refreshed debt, so the caller
 *  can update the row without a second round trip. */
export function useAddDebtPayment() {
  const action = useCallback(
    (input: { debtId: number; payload: DebtPaymentPayload }) =>
      apiFetch<DebtPaymentCreated>(endpoints.debts.addPayment(input.debtId), {
        method: 'POST',
        body: input.payload,
      }),
    [],
  )
  return useMutation(action, { invalidates: [cacheKeys.debts, cacheKeys.payments] })
}

export function useVoidDebtPayment() {
  const action = useCallback(
    (input: { id: number; reason: string }) =>
      apiFetch<DebtPayment>(endpoints.debtPayments.void(input.id), {
        method: 'POST',
        body: { reason: input.reason },
      }),
    [],
  )
  return useMutation(action, { invalidates: [cacheKeys.debts, cacheKeys.payments] })
}
