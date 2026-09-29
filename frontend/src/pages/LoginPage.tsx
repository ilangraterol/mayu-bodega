import { useState } from 'react'
import type { FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '../components/ui/Button'
import { ErrorBanner } from '../components/ui/Feedback'
import { TextInput } from '../components/ui/Field'
import { useAuth } from '../hooks/useAuth'
import { ApiError } from '../lib/apiClient'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<ApiError | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await login(username.trim(), password)
      navigate('/', { replace: true })
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught : new ApiError(0, 'No se pudo iniciar sesión.', {}),
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col justify-center px-5 py-10">
      <div className="mx-auto w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex size-14 items-center justify-center rounded-2xl bg-slate-900 text-2xl">
            🏪
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Mayu Bodega</h1>
          <p className="mt-1 text-sm text-slate-500">Inventario, ventas y crédito</p>
        </div>

        <form onSubmit={onSubmit} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
          <TextInput
            label="Usuario"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            required
            autoFocus
          />
          <TextInput
            label="Contraseña"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />

          {error ? <ErrorBanner error={error} /> : null}

          <Button type="submit" size="lg" fullWidth isLoading={isSubmitting}>
            Entrar
          </Button>
        </form>
      </div>
    </div>
  )
}
