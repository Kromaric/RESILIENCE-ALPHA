import { useEffect, useState } from 'react'
import { api } from './client'

// Lit une route GET de bo-api, et la relit toutes les `refreshMs` millisecondes si demandé.
// En cas d'échec d'un rafraîchissement, la dernière donnée reçue reste affichée.
export function useApi(path, { refreshMs } = {}) {
  const [state, setState] = useState({ path, data: undefined, error: null })

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const data = await api(path)
        if (!cancelled) setState({ path, data, error: null })
      } catch (error) {
        if (!cancelled) setState((s) => ({ path, data: s.path === path ? s.data : undefined, error }))
      }
    }
    load()
    const timer = refreshMs ? setInterval(load, refreshMs) : null
    return () => {
      cancelled = true
      if (timer) clearInterval(timer)
    }
  }, [path, refreshMs])

  const current = state.path === path ? state : { data: undefined, error: null }
  return {
    data: current.data,
    error: current.error,
    loading: current.data === undefined && !current.error,
  }
}
