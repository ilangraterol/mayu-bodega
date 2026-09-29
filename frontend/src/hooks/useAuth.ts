/**
 * Session context. It lives outside the provider component so that importing
 * `useAuth` never pulls the provider into a module that also exports hooks,
 * which keeps React Fast Refresh working during development.
 */

import { createContext, useContext } from 'react'

import type { Role, User } from '../types/api'

export interface AuthContextValue {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<User>
  logout: () => Promise<void>
  hasRole: (...roles: Role[]) => boolean
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth debe usarse dentro de <AuthProvider>')
  return context
}
