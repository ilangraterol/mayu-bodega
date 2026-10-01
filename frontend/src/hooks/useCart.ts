/**
 * Cart state for the point of sale.
 *
 * Kept in a reducer so the cart survives re-renders without persisting to
 * storage: a half-finished sale must not leak into the next session. Totals are
 * always recomputed by the server through `POST /sales/quote/`, because the BCV
 * rate and the configured surcharge are server-owned.
 */

import { useCallback, useMemo, useReducer } from 'react'

import { parseMoney, roundQuantity, toQuantityString } from '../lib/money'
import type { Product, SaleItemInput, SurchargeSource } from '../types/api'

/**
 * A line keeps the percentage the cashier settled on. It starts at whatever the
 * catalogue resolves (article > category > store) and is only sent to the
 * server once the cashier actually edits it, so confirming a value that matches
 * the catalogue never pins it onto the article.
 */
export interface CartLine {
  product: Product
  quantity: number
  /** `null` means "not chosen yet": the server resolves it from the catalogue. */
  surchargePercentage: number | null
  /** The percentage the catalogue resolves, used to pre-fill and to reset. */
  inheritedPercentage: number
  /** Why the inherited value is what it is, shown next to the picker. */
  inheritedSource: SurchargeSource
}

type Action =
  | { type: 'add'; product: Product; quantity?: number }
  | { type: 'increment'; productId: number }
  | { type: 'decrement'; productId: number }
  | { type: 'setQuantity'; productId: number; quantity: number }
  | { type: 'setSurcharge'; productId: number; percentage: number | null }
  | { type: 'remove'; productId: number }
  | { type: 'clear' }

function inheritedOf(product: Product): number {
  return parseMoney(product.effective_surcharge_percentage ?? '0')
}

function reducer(state: CartLine[], action: Action): CartLine[] {
  switch (action.type) {
    case 'add': {
      const existing = state.find((line) => line.product.id === action.product.id)
      if (!existing) {
        return [
          ...state,
          {
            product: action.product,
            quantity: action.quantity ?? 1,
            surchargePercentage: null,
            inheritedPercentage: inheritedOf(action.product),
            inheritedSource: action.product.surcharge_source,
          },
        ]
      }
      return state.map((line) =>
        line.product.id === action.product.id
          ? { ...line, quantity: roundQuantity(line.quantity + (action.quantity ?? 1)) }
          : line,
      )
    }
    case 'increment':
      return state.map((line) =>
        line.product.id === action.productId
          ? { ...line, quantity: roundQuantity(line.quantity + 1) }
          : line,
      )
    case 'decrement':
      return state.map((line) =>
        line.product.id === action.productId
          ? { ...line, quantity: roundQuantity(line.quantity - 1) }
          : line,
      )
    case 'setQuantity':
      return state.map((line) =>
        line.product.id === action.productId
          ? { ...line, quantity: roundQuantity(Math.max(0, action.quantity)) }
          : line,
      )
    case 'setSurcharge':
      return state.map((line) =>
        line.product.id === action.productId
          ? { ...line, surchargePercentage: action.percentage }
          : line,
      )
    case 'remove':
      return state.filter((line) => line.product.id !== action.productId)
    case 'clear':
      return []
  }
}

export interface CartApi {
  lines: CartLine[]
  /** Units of a product already in the cart, for the grid badge. */
  quantityOf: (productId: number) => number
  add: (product: Product) => void
  increment: (productId: number) => void
  decrement: (productId: number) => void
  setQuantity: (productId: number, quantity: number) => void
  /** The percentage this line will be charged at, chosen or inherited. */
  surchargeOf: (productId: number) => number
  /** `null` hands the decision back to the catalogue. */
  setSurcharge: (productId: number, percentage: number | null) => void
  /** How many lines carry a percentage the cashier chose. */
  customisedCount: number
  remove: (productId: number) => void
  clear: () => void
  isEmpty: boolean
  count: number
  /** Client-side estimate only; the server quote is authoritative. */
  estimatedSubtotalUsd: number
  /** Some line needs more units than the store physically has. */
  hasShortage: boolean
  toPayload: () => SaleItemInput[]
}

export function useCart(): CartApi {
  const [lines, dispatch] = useReducer(reducer, [])

  const add = useCallback(
    (product: Product) => dispatch({ type: 'add', product }),
    [],
  )
  const increment = useCallback(
    (productId: number) => dispatch({ type: 'increment', productId }),
    [],
  )
  const decrement = useCallback(
    (productId: number) => dispatch({ type: 'decrement', productId }),
    [],
  )
  const setQuantity = useCallback(
    (productId: number, quantity: number) =>
      dispatch({ type: 'setQuantity', productId, quantity }),
    [],
  )
  const setSurcharge = useCallback(
    (productId: number, percentage: number | null) =>
      dispatch({ type: 'setSurcharge', productId, percentage }),
    [],
  )
  const remove = useCallback(
    (productId: number) => dispatch({ type: 'remove', productId }),
    [],
  )
  const clear = useCallback(() => dispatch({ type: 'clear' }), [])

  const quantityOf = useCallback(
    (productId: number) => lines.find((line) => line.product.id === productId)?.quantity ?? 0,
    [lines],
  )

  const surchargeOf = useCallback(
    (productId: number) => {
      const line = lines.find((entry) => entry.product.id === productId)
      return line?.surchargePercentage ?? line?.inheritedPercentage ?? 0
    },
    [lines],
  )

  const derived = useMemo(() => {
    const count = lines.reduce((total, line) => total + line.quantity, 0)
    const estimatedSubtotalUsd = lines.reduce(
      (total, line) => total + line.quantity * parseMoney(line.product.price_usd),
      0,
    )
    // Stock zero is only sellable when the store allows it; otherwise the server
    // rejects the line. Surfacing it early lets the cashier swap the product.
    const hasShortage = lines.some(
      (line) => line.quantity > parseMoney(line.product.stock),
    )
    const customisedCount = lines.filter((line) => line.surchargePercentage !== null).length
    return { count, estimatedSubtotalUsd, hasShortage, customisedCount }
  }, [lines])

  const toPayload = useCallback(
    (): SaleItemInput[] =>
      lines
        .filter((line) => line.quantity > 0)
        .map((line) => ({
          product_id: line.product.id,
          quantity: toQuantityString(line.quantity),
          // Only a deliberate choice travels. Omitting it lets the backend keep
          // resolving the catalogue, which is what avoids pinning a value that
          // merely happened to match.
          ...(line.surchargePercentage === null
            ? {}
            : { surcharge_percentage: String(line.surchargePercentage) }),
        })),
    [lines],
  )

  return {
    lines,
    quantityOf,
    add,
    increment,
    decrement,
    setQuantity,
    surchargeOf,
    setSurcharge,
    customisedCount: derived.customisedCount,
    remove,
    clear,
    isEmpty: lines.length === 0,
    count: derived.count,
    estimatedSubtotalUsd: derived.estimatedSubtotalUsd,
    hasShortage: derived.hasShortage,
    toPayload,
  }
}
