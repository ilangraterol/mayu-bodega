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
import type { Product, SaleItemInput } from '../types/api'

export interface CartLine {
  product: Product
  quantity: number
}

type Action =
  | { type: 'add'; product: Product; quantity?: number }
  | { type: 'increment'; productId: number }
  | { type: 'decrement'; productId: number }
  | { type: 'setQuantity'; productId: number; quantity: number }
  | { type: 'remove'; productId: number }
  | { type: 'clear' }

function reducer(state: CartLine[], action: Action): CartLine[] {
  switch (action.type) {
    case 'add': {
      const existing = state.find((line) => line.product.id === action.product.id)
      if (!existing) {
        return [...state, { product: action.product, quantity: action.quantity ?? 1 }]
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
  const remove = useCallback(
    (productId: number) => dispatch({ type: 'remove', productId }),
    [],
  )
  const clear = useCallback(() => dispatch({ type: 'clear' }), [])

  const quantityOf = useCallback(
    (productId: number) => lines.find((line) => line.product.id === productId)?.quantity ?? 0,
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
    return { count, estimatedSubtotalUsd, hasShortage }
  }, [lines])

  const toPayload = useCallback(
    (): SaleItemInput[] =>
      lines
        .filter((line) => line.quantity > 0)
        .map((line) => ({
          product_id: line.product.id,
          quantity: toQuantityString(line.quantity),
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
    remove,
    clear,
    isEmpty: lines.length === 0,
    count: derived.count,
    estimatedSubtotalUsd: derived.estimatedSubtotalUsd,
    hasShortage: derived.hasShortage,
    toPayload,
  }
}
