import { createContext, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from '../api/client'

const AuthContext = createContext(null)

// Connexion au back-office, dans l'ordre imposé : identifiant → visage (caméra USB) → mot de
// passe. auth-service pilote la LED de l'ESP8266 à chaque étape.
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

  // 1. Identifiant → { session_id, step: "face" | "password", face_challenge, face_enrollment_required }
  function identify(email) {
    return api('/bo/auth/identify', { method: 'POST', body: { email }, auth: false })
  }

  // 2. Images de la caméra → { step: "password" }
  function verifyFace(sessionId, frames) {
    return api('/bo/auth/face', {
      method: 'POST',
      body: { session_id: sessionId, frames },
      auth: false,
    })
  }

  // 3. Mot de passe → session ouverte, ou jeton d'enrôlement (démarrage : aucun visage enregistré)
  async function submitPassword(sessionId, password) {
    const token = await api('/bo/auth/password', {
      method: 'POST',
      body: { session_id: sessionId, password },
      auth: false,
    })
    if (token.face_enrollment_required) return { enrollmentToken: token.access_token }
    setToken(token.access_token)
    setOperator(await api('/bo/auth/me'))
    return {}
  }

  // Démarrage : le premier administrateur enregistre son visage, puis se reconnecte
  function enrollOwnFace(enrollmentToken, frames) {
    return api('/bo/auth/enroll-face', {
      method: 'POST',
      body: { consent: true, frames },
      auth: false,
      token: enrollmentToken,
    })
  }

  // Habilitations : l'opérateur connecté vient de modifier son propre nom ou rôle
  function updateOperator(changes) {
    setOperator((current) => (current ? { ...current, ...changes } : current))
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
    <AuthContext.Provider
      value={{
        operator,
        checking,
        identify,
        verifyFace,
        submitPassword,
        enrollOwnFace,
        updateOperator,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
