// Client HTTP de bo-api : jeton opérateur et format d'erreur {"detail": {"code", "message"}}
const TOKEN_KEY = 'orbe.bo.token'

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // stockage indisponible : la session ne survivra pas au rechargement
  }
}

// Appelé quand bo-api répond 401 (jeton expiré, session révoquée) : retour à la connexion
let onUnauthorized = () => {}
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

export class ApiError extends Error {
  constructor(status, code, message, retryAfter = null) {
    super(message)
    this.status = status
    this.code = code
    this.retryAfter = retryAfter
  }
}

const UNREACHABLE = 'bo-api injoignable. La pile de développement est-elle lancée ?'

export async function api(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'network_error', UNREACHABLE)
  }

  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (res.ok) return data

  const detail = data?.detail
  if (!detail?.code) {
    // Réponse qui ne vient pas de bo-api (proxy Vite ou Nginx sans back derrière)
    throw new ApiError(res.status, 'http_error', res.status >= 500 ? UNREACHABLE : `Erreur ${res.status}`)
  }
  if (res.status === 401 && auth) onUnauthorized()
  throw new ApiError(res.status, detail.code, detail.message, res.headers.get('Retry-After'))
}
