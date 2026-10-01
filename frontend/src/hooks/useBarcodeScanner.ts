/**
 * Barcode entry: resolves a scan and hands the product to the cart.
 *
 * The same field is also the free-text search, so the lookup must not run on
 * every keystroke: a partial word is not a barcode and `barcode_lookup` answers
 * 404, which used to report "not found" while the grid was full of matches. The
 * lookup is therefore triggered by Enter, which every hardware scanner appends
 * as a suffix, and by a short digit-only string in case one is configured
 * without it.
 *
 * The callback is kept in a ref instead of an effect dependency: the cart object
 * is recreated on every render, and depending on it would re-run the resolution
 * and add the same product repeatedly.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError, apiFetch } from '../lib/apiClient'
import { endpoints } from '../lib/endpoints'
import type { Product } from '../types/api'

interface UseBarcodeScannerOptions {
  onResolved: (product: Product) => void
}

type ScannerState = 'idle' | 'resolving' | 'not_found'

const DEBOUNCE_MS = 250
/** Only digits can be a barcode; letters are the cashier typing a name. */
const BARCODE_SHAPE = /^\d+$/
const MIN_BARCODE_LENGTH = 4

export function useBarcodeScanner({ onResolved }: UseBarcodeScannerOptions) {
  const [code, setCode] = useState('')
  const [state, setState] = useState<ScannerState>('idle')

  const onResolvedRef = useRef(onResolved)
  useEffect(() => {
    onResolvedRef.current = onResolved
  })

  const resolve = useCallback(async (value: string) => {
    setState('resolving')
    try {
      const product = await apiFetch<Product>(endpoints.products.barcodeLookup(value))
      onResolvedRef.current(product)
      setState('idle')
      return true
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setState('not_found')
        return false
      }
      // Any other failure keeps the code so the cashier can correct it.
      setState('idle')
      return false
    }
  }, [])

  // A scanner configured without a trailing Enter still types digits fast, so a
  // complete-looking numeric string is resolved on its own.
  useEffect(() => {
    const value = code.trim()
    if (!BARCODE_SHAPE.test(value) || value.length < MIN_BARCODE_LENGTH) return

    let cancelled = false
    const timer = setTimeout(async () => {
      if (cancelled) return
      const found = await resolve(value)
      if (!cancelled && found) setCode('')
    }, DEBOUNCE_MS)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [code, resolve])

  function onSubmit(event: FormEvent) {
    // Enter must not reload the page: scanning is the primary interaction.
    event.preventDefault()
    const value = code.trim()
    if (!value) return
    void resolve(value).then((found) => {
      if (found) setCode('')
    })
  }

  function clear() {
    setCode('')
    setState('idle')
  }

  /** Drops a previous miss without touching the field the cashier is typing in. */
  function clearNotFound() {
    setState((current) => (current === 'not_found' ? 'idle' : current))
  }

  return {
    code,
    setCode,
    onSubmit,
    isResolving: state === 'resolving',
    notFound: state === 'not_found',
    clear,
    clearNotFound,
  }
}
