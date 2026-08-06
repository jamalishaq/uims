import { useEffect, useRef, useState } from 'react'
import { Outlet } from 'react-router-dom'
import useAuthStore from '../../store/authStore'
import api from '../../lib/api'
import Spinner from '../../components/ui/Spinner'

/**
 * Turn the refresh cookie back into a session, once, before rendering anything behind it.
 *
 * The access token is deliberately **not** persisted — see `authStore` — so every reload starts
 * without one even when the principal is remembered. This is what gets it back: one call to
 * `/auth/refresh`, which sends the `HttpOnly` cookie the browser holds.
 *
 * Blocking the first render is the point. Letting children mount first would have each of them
 * fire a request with no token, take a 401, and queue behind the interceptor's refresh — the
 * same outcome, several requests later, with a flash of empty state on the way.
 *
 * The `ref` guards React 18's StrictMode double-effect in development. Without it the second
 * run races the first, and one of the two refreshes lands after the other has already set the
 * token.
 */
export default function PersistLogin() {
  const accessToken = useAuthStore((s) => s.accessToken)
  const signIn = useAuthStore((s) => s.signIn)
  const signOut = useAuthStore((s) => s.signOut)
  const [checking, setChecking] = useState(!accessToken)
  const attempted = useRef(false)

  useEffect(() => {
    if (attempted.current || accessToken) return
    attempted.current = true

    api
      .post('/auth/refresh')
      .then(({ data }) => signIn(data))
      // A failure here is the ordinary case for a first-time visitor: no cookie, no session.
      // `RequireAuth` sends them to /login on the next render, so there is nothing to report.
      .catch(() => signOut())
      .finally(() => setChecking(false))
  }, [accessToken, signIn, signOut])

  if (checking) {
    return (
      <div className="grid h-dvh place-items-center bg-ink-100 dark:bg-ink-950">
        <Spinner size="lg" />
        <span className="sr-only">Restoring your session…</span>
      </div>
    )
  }

  return <Outlet />
}
