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

/**
 * Amount entry the way a till does it: the cashier types the céntimos and the
 * field shows the amount, so the decimal separator never has to be typed. "104"
 * becomes "1.04" and "45784" becomes "457.84". Only digits are read, so a stray
 * separator or letter cannot break the value.
 */
export function digitsToAmount(digits: string): string {
  const clean = digits.replace(/\D/g, '')
  if (clean === '') return ''
  return (Number.parseInt(clean, 10) / 100).toFixed(MONEY_PLACES)
}

/**
 * Works out the digits of a digits-based amount field after a keystroke.
 *
 * Reading the digits back off the input is ambiguous, because the field already
 * shows a separator: with "457.84" on screen, typing a "5" at the end arrives as
 * "457.845" and has to mean "45784" plus "5", not the digits "0457845". A typed
 * character is therefore recognised by checking that the value the field already
 * displayed is still a prefix of the new one. Anything else is a deletion, a
 * paste or a selection, and its digits are taken exactly as they arrived.
 */
export function nextAmountDigits(currentAmount: string, rawValue: string): string {
  const typed = rawValue.replace(/\D/g, '')
  if (currentAmount !== '' && rawValue.startsWith(currentAmount)) {
    return currentAmount.replace(/\D/g, '') + typed.slice(currentAmount.replace(/\D/g, '').length)
  }
  return typed
}

const usdFormatter = new Intl.NumberFormat('es-VE', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: MONEY_PLACES,
  maximumFractionDigits: MONEY_PLACES,
})

export function formatUsd(value: string | number | null | undefined): string {
  return usdFormatter.format(parseMoney(value))
}

/**
 * `USD 1.234,56` spelled out, which is the clear choice in totals and reports but
 * costs three characters of a phone-width price. The till grid uses this instead:
 * `narrowSymbol` renders `$1.234,56` in es-VE, and it is scoped here so the
 * unambiguous label survives everywhere else.
 */
const usdCompactFormatter = new Intl.NumberFormat('es-VE', {
  style: 'currency',
  currency: 'USD',
  currencyDisplay: 'narrowSymbol',
  minimumFractionDigits: MONEY_PLACES,
  maximumFractionDigits: MONEY_PLACES,
})

export function formatUsdCompact(value: string | number | null | undefined): string {
  return usdCompactFormatter.format(parseMoney(value))
}

const vesNumberFormatter = new Intl.NumberFormat('es-VE', {
  minimumFractionDigits: MONEY_PLACES,
  maximumFractionDigits: MONEY_PLACES,
})

export function formatVes(value: string | number | null | undefined): string {
  // The ISO code is the project's currency denomination: never "Bs." nor the
  // locale symbol. See AGENTS.md (Denominación de moneda).
  return `VES ${vesNumberFormatter.format(parseMoney(value))}`
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

/** A percentage without trailing zeros: "5.00" reads as "5%". */
export function formatPercent(value: string | number | null | undefined): string {
  const rounded = roundMoney(parseMoney(value), 2)
  return `${Number(rounded.toFixed(2))}%`
}
