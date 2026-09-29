/**
 * Money helpers.
 *
 * The API sends money as decimal strings, so all arithmetic happens here on
 * numbers parsed from those strings and is rounded back with `roundMoney` to
 * mirror the backend's ROUND_HALF_UP behaviour. Never use raw floats on money
 * coming from the API without passing through `parseMoney`.
 */

import { CURRENCY_VES, type Currency } from '../types/api'

export const MONEY_PLACES = 2
export const QUANTITY_PLACES = 3

/** Parse a decimal string (or number) into a JS number. */
export function parseMoney(value: string | number | null | undefined): number {
  if (value === null || value === undefined || value === '') return 0
  const parsed = typeof value === 'number' ? value : Number.parseFloat(value)
  return Number.isFinite(parsed) ? parsed : 0
}

/** Round to the money scale using half-up, matching the backend. */
export function roundMoney(value: number, places: number = MONEY_PLACES): number {
  const factor = 10 ** places
  // The epsilon nudge avoids 1.005 -> 1.00 from binary float representation.
  return Math.round((value + Number.EPSILON * Math.sign(value)) * factor) / factor
}

export function roundQuantity(value: number): number {
  return roundMoney(value, QUANTITY_PLACES)
}

/** Normalise a number to a fixed-decimal string for the API. */
export function toMoneyString(value: number | string, places: number = MONEY_PLACES): string {
  return roundMoney(parseMoney(value), places).toFixed(places)
}

export function toQuantityString(value: number | string): string {
  const rounded = roundQuantity(parseMoney(value))
  // Trim trailing zeros: "2.000" -> "2" keeps payloads small and readable.
  return String(rounded)
}

const usdFormatter = new Intl.NumberFormat('es-VE', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: MONEY_PLACES,
  maximumFractionDigits: MONEY_PLACES,
})

const vesFormatter = new Intl.NumberFormat('es-VE', {
  style: 'currency',
  currency: 'VES',
  minimumFractionDigits: MONEY_PLACES,
  maximumFractionDigits: MONEY_PLACES,
})

export function formatUsd(value: string | number | null | undefined): string {
  return usdFormatter.format(parseMoney(value))
}

export function formatVes(value: string | number | null | undefined): string {
  return vesFormatter.format(parseMoney(value))
}

export function formatMoney(
  value: string | number | null | undefined,
  currency: Currency = 'USD',
): string {
  return currency === CURRENCY_VES ? formatVes(value) : formatUsd(value)
}

/** Plain number for inputs and tables: "1.234,56" is fine for display. */
export function formatNumber(value: string | number | null | undefined, places = 0): string {
  return new Intl.NumberFormat('es-VE', {
    minimumFractionDigits: places,
    maximumFractionDigits: places,
  }).format(parseMoney(value))
}

/** The BCV rate, always shown with 4 decimals because it is a legal rate. */
export function formatRate(value: string | number | null | undefined): string {
  return new Intl.NumberFormat('es-VE', {
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  }).format(parseMoney(value))
}

/** Trims a whole unit: 3.000 -> "3", 3.500 -> "3,5". */
export function formatQuantity(value: string | number | null | undefined): string {
  const parsed = parseMoney(value)
  const rounded = roundQuantity(parsed)
  return new Intl.NumberFormat('es-VE', { maximumFractionDigits: QUANTITY_PLACES }).format(rounded)
}
