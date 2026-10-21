import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'

export default function RequireAuth() {
  const { operator, checking } = useAuth()
  const location = useLocation()

  if (checking) {
    return <p className="p-8 text-sm text-muted">Vérification de la session…</p>
  }
  if (!operator) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}
