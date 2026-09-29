/**
 * Minimal remote-state cache built on `useSyncExternalStore`.
 *
 * AGENTS.md forbids introducing a data library without approval, so this file
 * provides only what the app actually needs:
 *   - request de-duplication (two components, one request)
 *   - a short freshness window so remounting a screen does not refetch
 *   - stale-while-revalidate: cached data renders instantly, then refreshes
 *   - `invalidate()` so a mutation can bust the affected keys
 *
 * Two rules keep it correct, and both were learned the hard way:
 *
 * 1. A request is owned by the cache, not by the component that started it.
 *    Aborting on unmount would kill a request that other components are still
 *    waiting on, and under StrictMode (where effects run twice) it left every
 *    query stuck in `loading` forever: the first effect was aborted and the
 *    second one saw the key as already in flight.
 * 2. `invalidate()` bumps a revision that the fetch effect depends on, so a
 *    stale entry is actually refetched instead of just re-rendered.
 */

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from 'react'

import { ApiError, apiFetch } from './apiClient'

export type QueryStatus = 'idle' | 'loading' | 'success' | 'error'

export interface QueryEntry<T> {
  data: T | null
  error: ApiError | null
  status: QueryStatus
  /** True while a request is in flight, including a background revalidation. */
  isFetching: boolean
  updatedAt: number
}

const EMPTY: QueryEntry<never> = {
  data: null,
  error: null,
  status: 'idle',
  isFetching: false,
  updatedAt: 0,
}

const entries = new Map<string, QueryEntry<unknown>>()
const listeners = new Map<string, Set<() => void>>()
const inflight = new Map<string, Promise<unknown>>()

/** Bumped by `invalidate()` so mounted queries know they must refetch. */
let revision = 0
const revisionListeners = new Set<() => void>()

function read<T>(key: string): QueryEntry<T> {
  return (entries.get(key) as QueryEntry<T> | undefined) ?? (EMPTY as QueryEntry<T>)
}

function write<T>(key: string, next: QueryEntry<T>): void {
  // Always replace the object so `useSyncExternalStore` sees a new reference.
  entries.set(key, next as QueryEntry<unknown>)
  listeners.get(key)?.forEach((listener) => listener())
}

function subscribe(key: string, listener: () => void): () => void {
  const group = listeners.get(key) ?? new Set()
  group.add(listener)
  listeners.set(key, group)
  return () => {
    group.delete(listener)
  }
}

function getRevision(): number {
  return revision
}

function subscribeRevision(listener: () => void): () => void {
  revisionListeners.add(listener)
  return () => {
    revisionListeners.delete(listener)
  }
}

export interface EnsureOptions {
  staleTime: number
  path: string
}

/**
 * Fetch `key` if it is missing or stale. Safe to call on every render: it
 * de-duplicates and short-circuits.
 */
export function ensureQuery(key: string, { staleTime, path }: EnsureOptions): void {
  const entry = read(key)
  const isFresh = entry.status === 'success' && Date.now() - entry.updatedAt < staleTime
  if (isFresh || inflight.has(key)) return

  // Keep showing previous data while revalidating.
  write(key, {
    ...entry,
    isFetching: true,
    status: entry.data === null ? 'loading' : entry.status,
  })

  const request = apiFetch<unknown>(path)
    .then((data) => {
      inflight.delete(key)
      write(key, {
        data,
        error: null,
        status: 'success',
        isFetching: false,
        updatedAt: Date.now(),
      })
    })
    .catch((error: unknown) => {
      inflight.delete(key)
      const apiError =
        error instanceof ApiError ? error : new ApiError(0, 'Error inesperado.', {})
      // Stale data stays on screen; the banner explains the failure.
      write(key, {
        data: entry.data,
        error: apiError,
        status: 'error',
        isFetching: false,
        updatedAt: entry.updatedAt,
      })
    })

  inflight.set(key, request)
}

export interface QueryOptions {
  /** How long cached data is considered fresh. Default 30s. */
  staleTime?: number
  enabled?: boolean
}

export interface QueryResult<T> {
  data: T | null
  error: ApiError | null
  isLoading: boolean
  isFetching: boolean
  isError: boolean
  refetch: () => void
}

/**
 * GET a resource identified by a cache `key` (pass `null` to keep it disabled).
 */
export function useApiQuery<T>(
  key: string | null,
  path: string,
  options: QueryOptions = {},
): QueryResult<T> {
  const staleTime = options.staleTime ?? 30_000
  const enabled = options.enabled ?? true
  const activeKey = enabled && key !== null ? key : null

  const entry = useSyncExternalStore(
    useCallback(
      (listener: () => void) => (activeKey ? subscribe(activeKey, listener) : () => {}),
      [activeKey],
    ),
    useCallback(() => (activeKey ? read<T>(activeKey) : EMPTY), [activeKey]),
    useCallback(() => (activeKey ? read<T>(activeKey) : EMPTY), [activeKey]),
  )

  const cacheRevision = useSyncExternalStore(subscribeRevision, getRevision, getRevision)

  const [forced, setForced] = useState(0)
  const force = useCallback(() => setForced((value) => value + 1), [])

  useEffect(() => {
    if (!activeKey) return
    // No AbortController: this request belongs to the cache and to every other
    // component reading the same key.
    ensureQuery(activeKey, { staleTime, path })
  }, [activeKey, staleTime, path, forced, cacheRevision])

  const refetch = useCallback(() => {
    if (!activeKey) return
    force()
  }, [activeKey, force])

  return useMemo(
    () => ({
      data: entry.data,
      error: entry.error,
      isLoading: entry.status === 'loading' && entry.data === null,
      isFetching: entry.isFetching,
      isError: entry.status === 'error',
      refetch,
    }),
    [entry, refetch],
  )
}

/**
 * Mark every cache entry whose key starts with `prefix` as stale, then notify
 * subscribers so mounted screens refetch.
 */
export function invalidate(prefixes: string | string[]): void {
  const list = Array.isArray(prefixes) ? prefixes : [prefixes]
  let touched = false

  for (const [key, entry] of entries) {
    if (!list.some((prefix) => key.startsWith(prefix))) continue
    if (entry.status === 'idle') continue
    write(key, { ...entry, updatedAt: 0 })
    touched = true
  }

  if (touched) {
    revision += 1
    revisionListeners.forEach((listener) => listener())
  }
}

export function readQuery<T>(key: string): T | null {
  return read<T>(key).data
}
