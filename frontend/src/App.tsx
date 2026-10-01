import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'

import { AppLayout } from './components/layout/AppLayout'
import { useAuth } from './hooks/useAuth'
import type { Role } from './types/api'
import { CreditsPage } from './pages/CreditsPage'
import { CategoriesPage } from './pages/CategoriesPage'
import { DashboardPage } from './pages/DashboardPage'
import { LoginPage } from './pages/LoginPage'
import { ProductsPage } from './pages/ProductsPage'
import { SalesPage } from './pages/SalesPage'
import { SellPage } from './pages/SellPage'
import { SettingsPage } from './pages/SettingsPage'
import { FullPageLoader } from './components/ui/FullPageLoader'

/** Blocks a route until the session is known and the role is allowed. */
function Protected({ children, roles }: { children: ReactNode; roles?: Role[] }) {
  const { isAuthenticated, isLoading, hasRole } = useAuth()

  if (isLoading) return <FullPageLoader />
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (roles && !hasRole(...roles)) {
    return (
      <div className="py-16 text-center">
        <p className="text-3xl">🔒</p>
        <h2 className="mt-2 text-base font-semibold text-slate-800">Sin permisos</h2>
        <p className="mt-1 text-sm text-slate-500">
          Su rol no tiene acceso a esta sección.
        </p>
      </div>
    )
  }
  return <>{children}</>
}

export function App() {
  const { isAuthenticated, isLoading } = useAuth()

  return (
    <Routes>
      <Route
        path="/login"
        element={isLoading ? <FullPageLoader /> : isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />

      <Route
        element={
          <Protected>
            <AppLayout />
          </Protected>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route
          path="vender"
          element={
            <Protected roles={['CAJERO', 'GERENTE']}>
              <SellPage />
            </Protected>
          }
        />
        <Route
          path="ventas"
          element={
            <Protected roles={['CAJERO', 'GERENTE']}>
              <SalesPage />
            </Protected>
          }
        />
        <Route
          path="productos"
          element={
            <Protected roles={['ALMACENERO', 'GERENTE']}>
              <ProductsPage />
            </Protected>
          }
        />
        {/* Categories share the catalogue permissions, so they sit next to it. */}
        <Route
          path="categorias"
          element={
            <Protected roles={['ALMACENERO', 'GERENTE']}>
              <CategoriesPage />
            </Protected>
          }
        />
        <Route path="creditos" element={<CreditsPage />} />
        <Route path="ajustes" element={<SettingsPage />} />
      </Route>

      <Route
        path="*"
        element={
          <div className="flex min-h-dvh flex-col items-center justify-center px-6 text-center">
            <p className="text-4xl">🧭</p>
            <h1 className="mt-2 text-lg font-semibold text-slate-800">Página no encontrada</h1>
            <a href="/" className="mt-3 text-sm text-slate-600 underline">
              Volver al inicio
            </a>
          </div>
        }
      />
    </Routes>
  )
}
