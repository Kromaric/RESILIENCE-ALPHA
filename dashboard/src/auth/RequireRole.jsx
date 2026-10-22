import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'

// Pages réservées à un rôle (Habilitations : admin). bo-api et auth-service revérifient de
// toute façon le rôle : ce garde n'évite qu'un écran d'erreurs.
export default function RequireRole({ role }) {
  const { operator } = useAuth()
  if (operator?.role !== role) return <Navigate to="/" replace />
  return <Outlet />
}
