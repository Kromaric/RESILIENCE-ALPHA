import { createContext, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [operator, setOperator] = useState(null)
  // Un jeton est déjà stocké : on le vérifie auprès de bo-api avant d'afficher quoi que ce soit
  const [checking, setChecking] = useState(() => Boolean(getToken()))

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setToken(null)
      setOperator(null)
    })
    if (!getToken()) return
    api('/bo/auth/me')
      .then(setOperator)
      .catch(() => setToken(null))
      .finally(() => setChecking(false))
  }, [])

  async function login(email, password) {
    const { access_token } = await api('/bo/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
    })
    setToken(access_token)
    setOperator(await api('/bo/auth/me'))
  }

  async function logout() {
    try {
      await api('/bo/auth/logout', { method: 'POST' })
    } catch {
      // session déjà expirée ou bo-api injoignable : on déconnecte localement quand même
    } finally {
      setToken(null)
      setOperator(null)
    }
  }

  return (
    <AuthContext.Provider value={{ operator, checking, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}
