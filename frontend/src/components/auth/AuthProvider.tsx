/**
 * Restores the session from the stored token and owns login/logout.
 *
 * The token is kept in localStorage; the server is still the source of truth,
 * so a revoked token simply results in a redirect to the login screen.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { AuthContext } from '../../hooks/useAuth'
import type { AuthContextValue } from '../../hooks/useAuth'
import { ApiError, getToken, setToken } from '../../lib/apiClient'
import { endpoints } from '../../lib/endpoints'
import { invalidate } from '../../lib/queryCache'
import type { LoginResponse, User } from '../../types/api'

/** Cache prefixes owned by the previous user; dropped on logout. */
const PRIVATE_CACHE_PREFIXES = [
  'products',
  'product-images',
  'rates',
  'customers',
  'sales',
  'debts',
  'debt-payments',
  'stock-movements',
  'goods-entries',
  'exit-notes',
  'store-config',
  'sales-summary',
]

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  // Read the token once: with no token there is nothing to restore, so the app
  // can render the login screen immediately instead of a loading state.
  const [isLoading, setIsLoading] = useState(() => getToken() !== null)

  // Restore the session from the stored token on first render.
  useEffect(() => {
    if (!getToken()) return

    let cancelled = false

    fetch(endpoints.auth.me, { headers: { Authorization: `Token ${getToken()}` } })
      .then((response) => {
        if (response.status === 401) {
          setToken(null)
          return null
        }
        if (!response.ok) return null
        return response.json() as Promise<User>
      })
      .then((restored) => {
        if (!cancelled) setUser(restored)
      })
      .catch(() => {
        // A network failure must not wipe the token; the user can retry.
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const response = await fetch(endpoints.auth.login, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })

    const body: unknown = await response.json().catch(() => null)
    if (!response.ok) {
      const detail =
        body && typeof body === 'object' && 'detail' in body
          ? String((body as { detail: unknown }).detail)
          : 'No se pudo iniciar sesión.'
      throw new ApiError(response.status, detail, {})
    }

    const payload = body as LoginResponse
    setToken(payload.token)
    setUser(payload.user)
    return payload.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await fetch(endpoints.auth.logout, {
        method: 'POST',
        headers: { Authorization: `Token ${getToken() ?? ''}` },
      })
    } catch {
      // The token is revoked server-side; drop it locally regardless.
    } finally {
      setToken(null)
      setUser(null)
      // Every cached screen belongs to the previous user.
      invalidate(PRIVATE_CACHE_PREFIXES)
    }
  }, [])

  const hasRole = useCallback(
    (...roles: Parameters<AuthContextValue['hasRole']>) => {
      if (!user) return false
      if (user.roles.includes('ADMIN')) return true
      return roles.some((role) => user.roles.includes(role))
    },
    [user],
  )

  const value = useMemo<AuthContextValue>(
    () => ({ user, isLoading, isAuthenticated: user !== null, login, logout, hasRole }),
    [user, isLoading, login, logout, hasRole],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
