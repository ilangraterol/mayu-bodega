/**
 * Barcode entry: resolves a scan and hands the product to the cart.
 *
 * Hardware scanners type very fast, so the lookup is debounced and runs once per
 * scan. The callback is kept in a ref instead of an effect dependency: the cart
 * object is recreated on every render, and depending on it would re-run the
 * resolution and add the same product repeatedly.
 */

import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError, apiFetch } from '../lib/apiClient'
import { endpoints } from '../lib/endpoints'
import type { Product } from '../types/api'

interface UseBarcodeScannerOptions {
  onResolved: (product: Product) => void
}

type ScannerState = 'idle' | 'resolving' | 'not_found'

const DEBOUNCE_MS = 250

export function useBarcodeScanner({ onResolved }: UseBarcodeScannerOptions) {
  const [code, setCode] = useState('')
  const [state, setState] = useState<ScannerState>('idle')

  const onResolvedRef = useRef(onResolved)
  useEffect(() => {
    onResolvedRef.current = onResolved
  })

  useEffect(() => {
    const value = code.trim()
    if (!value) return

    let cancelled = false
    const timer = setTimeout(async () => {
      setState('resolving')
      try {
        const product = await apiFetch<Product>(endpoints.products.barcodeLookup(value))
        if (cancelled) return
        onResolvedRef.current(product)
        setCode('')
        setState('idle')
      } catch (error) {
        if (cancelled) return
        if (error instanceof ApiError && error.status === 404) {
          setCode('')
          setState('not_found')
        }
        // Any other failure keeps the code so the cashier can correct it.
      }
    }, DEBOUNCE_MS)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [code])

  function onSubmit(event: FormEvent) {
    // Enter must not reload the page: scanning is the primary interaction.
    event.preventDefault()
  }

  function clear() {
    setCode('')
    setState('idle')
  }

  return {
    code,
    setCode,
    onSubmit,
    isResolving: state === 'resolving',
    notFound: state === 'not_found',
    clear,
  }
}
