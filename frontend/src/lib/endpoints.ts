/**
 * Every API path in one place, so screens never hand-build a URL.
 *
 * The backend mounts each app's router at `api/` (see `config/urls.py`), so the
 * prefix is the resource name itself: `api/products/`, `api/sales/`, `api/rates/`.
 * Only `core` is namespaced, at `api/core/`. The mapping below is verified
 * against each viewset's `@action` names.
 */

import { toQuery } from './apiClient'

export const endpoints = {
  auth: {
    login: '/api/core/auth/login/',
    logout: '/api/core/auth/logout/',
    me: '/api/core/auth/me/',
  },
  storeConfig: {
    // The router exposes list at `config/store` and the singleton detail at
    // `config/store/{pk}`; the pk is irrelevant because the viewset always
    // loads the singleton row.
    list: '/api/core/config/store/',
    detail: (pk = 1) => `/api/core/config/store/${pk}/`,
  },
  products: {
    list: (params?: Record<string, string | number | boolean | undefined>) =>
      `/api/products/${toQuery(params ?? {})}`,
    detail: (id: number) => `/api/products/${id}/`,
    unitChoices: '/api/products/unit-choices/',
    barcodeLookup: (code: string) => `/api/products/barcode_lookup/${toQuery({ code })}`,
  },
  productImages: {
    list: (product: number) => `/api/product-images/${toQuery({ product })}`,
    detail: (id: number) => `/api/product-images/${id}/`,
    setPrimary: (id: number) => `/api/product-images/${id}/set_primary/`,
    upload: '/api/product-images/',
  },
  rates: {
    list: (params?: Record<string, string | number | boolean | undefined>) =>
      `/api/rates/${toQuery(params ?? {})}`,
    detail: (id: number) => `/api/rates/${id}/`,
    current: '/api/rates/current/',
    sync: '/api/rates/sync/',
    syncStatus: '/api/rates/sync-status/',
    manual: '/api/rates/manual/',
  },
  customers: {
    list: (params?: Record<string, string | number | boolean | undefined>) =>
      `/api/customers/${toQuery(params ?? {})}`,
    detail: (id: number) => `/api/customers/${id}/`,
    statement: (id: number) => `/api/customers/${id}/statement/`,
  },
  sales: {
    list: (params?: Record<string, string | number | boolean | undefined>) =>
      `/api/sales/${toQuery(params ?? {})}`,
    detail: (id: number) => `/api/sales/${id}/`,
    quote: '/api/sales/quote/',
    void: (id: number) => `/api/sales/${id}/void/`,
    summary: '/api/sales-summary/',
  },
  debts: {
    list: (params?: Record<string, string | number | boolean | undefined>) =>
      `/api/debts/${toQuery(params ?? {})}`,
    detail: (id: number) => `/api/debts/${id}/`,
    addPayment: (id: number) => `/api/debts/${id}/payments/`,
  },
  debtPayments: {
    list: (params?: Record<string, string | number | boolean | undefined>) =>
      `/api/debt-payments/${toQuery(params ?? {})}`,
    void: (id: number) => `/api/debt-payments/${id}/void/`,
  },
  movements: {
    list: (params?: Record<string, string | number | boolean | undefined>) =>
      `/api/stock-movements/${toQuery(params ?? {})}`,
  },
  goodsEntries: {
    list: (params?: Record<string, string | number | boolean | undefined>) =>
      `/api/goods-entries/${toQuery(params ?? {})}`,
    detail: (id: number) => `/api/goods-entries/${id}/`,
    cancel: (id: number) => `/api/goods-entries/${id}/cancel/`,
  },
  exitNotes: {
    list: (params?: Record<string, string | number | boolean | undefined>) =>
      `/api/exit-notes/${toQuery(params ?? {})}`,
    detail: (id: number) => `/api/exit-notes/${id}/`,
    reasons: '/api/exit-notes/reasons/',
    cancel: (id: number) => `/api/exit-notes/${id}/cancel/`,
  },
} as const

/** Cache key prefixes used by `invalidate()` after a mutation. */
export const cacheKeys = {
  products: 'products',
  productImages: 'product-images',
  rates: 'rates',
  customers: 'customers',
  sales: 'sales',
  summary: 'sales-summary',
  debts: 'debts',
  payments: 'debt-payments',
  movements: 'stock-movements',
  entries: 'goods-entries',
  exitNotes: 'exit-notes',
  config: 'store-config',
} as const
