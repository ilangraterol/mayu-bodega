/**
 * Unified HTTP client. Every request in the app goes through `apiFetch` so that
 * auth, error normalisation and JSON handling live in exactly one place.
 */

const TOKEN_KEY = 'mayu.token'

export class ApiError extends Error {
  readonly status: number
  /** Field errors keyed by field name, as returned by DRF. */
  readonly fieldErrors: Record<string, string[]>
  readonly detail: string | null

  constructor(status: number, detail: string | null, fieldErrors: Record<string, string[]>) {
    super(detail ?? `Error ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.fieldErrors = fieldErrors
  }

  get isUnauthorized(): boolean {
    return this.status === 401
  }

  get isConflict(): boolean {
    return this.status === 409
  }
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

/** DRF error bodies are either `{detail}` or `{field: [messages]}`. */
function normaliseErrorBody(status: number, body: unknown): ApiError {
  if (body && typeof body === 'object' && !Array.isArray(body)) {
    const record = body as Record<string, unknown>
    const fieldErrors: Record<string, string[]> = {}
    for (const [key, value] of Object.entries(record)) {
      if (Array.isArray(value)) {
        fieldErrors[key] = value.map((item) => String(item))
      }
    }
    const detail = typeof record.detail === 'string' ? record.detail : null
    if (detail) return new ApiError(status, detail, fieldErrors)
    const firstField = Object.keys(fieldErrors)[0]
    if (firstField) return new ApiError(status, fieldErrors[firstField].join(' '), fieldErrors)
  }
  if (typeof body === 'string' && body.trim()) {
    return new ApiError(status, body, {})
  }
  return new ApiError(status, null, {})
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
  /** Set for multipart uploads: the browser must add its own boundary. */
  formData?: FormData
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, formData } = options
  const headers: Record<string, string> = { Accept: 'application/json' }

  const token = getToken()
  if (token) headers.Authorization = `Token ${token}`

  let payload: BodyInit | undefined
  if (formData) {
    payload = formData
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let response: Response
  try {
    response = await fetch(path, { method, headers, body: payload, signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'No se pudo conectar con el servidor. Revise su conexión.', {})
  }

  if (response.status === 204) return undefined as T

  const isJson = (response.headers.get('Content-Type') ?? '').includes('application/json')
  const parsed: unknown = isJson ? await response.json().catch(() => null) : null

  if (!response.ok) {
    const error = normaliseErrorBody(response.status, parsed)
    // A dead token must not leave the app in a half-authenticated state.
    if (response.status === 401) setToken(null)
    throw error
  }

  return parsed as T
}

/** Builds a query string, dropping empty values so filters stay clean. */
export function toQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const query = search.toString()
  return query ? `?${query}` : ''
}
