/**
 * Opens a catalogue article as soon as the typed text is an exact barcode.
 *
 * The grid filter answers "what matches this text", which is the wrong question
 * for a barcode: a barcode is an exact identity, not a query, and it should open
 * the article even when the active chips would hide it from the list. So this asks
 * `barcode_lookup` for an exact hit instead of reading the page of results.
 *
 * A request is made only for a digit string long enough to be a barcode, and only
 * while the text keeps changing, so searching by name never reaches the API. A
 * miss is silent on purpose: the list below still filters normally, and showing
 * "not found" next to a full grid of matches was the bug this avoids.
 */

import { useEffect, useRef } from 'react'

import { apiFetch } from '../lib/apiClient'
import { endpoints } from '../lib/endpoints'
import type { Product } from '../types/api'
import { BARCODE_SHAPE, MIN_BARCODE_LENGTH } from './useBarcodeScanner'

const DEBOUNCE_MS = 300

interface UseExactBarcodeOpenOptions {
  value: string
  onMatch: (product: Product) => void
}

export function useExactBarcodeOpen({ value, onMatch }: UseExactBarcodeOpenOptions) {
  const onMatchRef = useRef(onMatch)
  useEffect(() => {
    onMatchRef.current = onMatch
  })

  useEffect(() => {
    const code = value.trim()
    if (!BARCODE_SHAPE.test(code) || code.length < MIN_BARCODE_LENGTH) return

    let cancelled = false
    const timer = setTimeout(async () => {
      try {
        const product = await apiFetch<Product>(endpoints.products.barcodeLookup(code))
        if (!cancelled) onMatchRef.current(product)
      } catch {
        // Nothing is shown on purpose. A 404 means the digits are not a barcode
        // yet, and any other failure is already reported by the list query
        // below through its own error state.
      }
    }, DEBOUNCE_MS)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [value])
}
