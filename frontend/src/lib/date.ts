/** Date formatting. The backend stores and serves ISO-8601 with an offset. */

/**
 * A bare `YYYY-MM-DD` is a calendar day, not an instant: parsing it as UTC would
 * shift it to the previous day for anyone behind Greenwich. Read it as local.
 */
const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/

function toDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const date = DATE_ONLY.test(value)
    ? new Date(Number(value.slice(0, 4)), Number(value.slice(5, 7)) - 1, Number(value.slice(8, 10)))
    : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDate(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  return new Intl.DateTimeFormat('es-VE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(date)
}

export function formatDateTime(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  return new Intl.DateTimeFormat('es-VE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

/** The 12-hour clock, built by hand because `Intl` with `es-VE` writes `a. m.`. */
function amPm(date: Date, { padHours }: { padHours: boolean }): string {
  const hours24 = date.getHours()
  const hours12 = String(hours24 % 12 === 0 ? 12 : hours24 % 12)
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const suffix = hours24 < 12 ? 'am' : 'pm'
  return `${padHours ? hours12.padStart(2, '0') : hours12}:${minutes} ${suffix}`
}

function dayMonthYear(date: Date): string {
  const day = String(date.getDate()).padStart(2, '0')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  return `${day}/${month}/${date.getFullYear()}`
}

/** `29/08/2026 11:00 am`. */
export function formatDateTimeAmPm(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  return `${dayMonthYear(date)} ${amPm(date, { padHours: true })}`
}

/**
 * `Lunes 29/09/2026 8:33 am`.
 *
 * The weekday comes from `Intl` and is capitalised by hand. The hour is not
 * zero-padded, unlike `formatDateTimeAmPm`, because this label sits in the header
 * where the day name already sets the rhythm.
 */
export function formatDayDateTime(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  const weekday = new Intl.DateTimeFormat('es-VE', { weekday: 'long' }).format(date)
  const capitalised = weekday.charAt(0).toUpperCase() + weekday.slice(1)
  return `${capitalised} ${dayMonthYear(date)} ${amPm(date, { padHours: false })}`
}

/** `YYYY-MM-DD` in local time, for `<input type="date">`. */
export function toDateInput(value: Date = new Date()): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/** `YYYY-MM-DDTHH:mm` in local time, for `<input type="datetime-local">`. */
export function toDateTimeInput(value: Date = new Date()): string {
  const hours = String(value.getHours()).padStart(2, '0')
  const minutes = String(value.getMinutes()).padStart(2, '0')
  return `${toDateInput(value)}T${hours}:${minutes}`
}

/** Human-friendly "hace 5 min" for recent activity lists. */
export function formatRelative(value: string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  const seconds = Math.round((Date.now() - date.getTime()) / 1000)
  if (seconds < 60) return 'hace un momento'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `hace ${minutes} min`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `hace ${hours} h`
  const days = Math.round(hours / 24)
  if (days < 30) return `hace ${days} d`
  return formatDate(value)
}
