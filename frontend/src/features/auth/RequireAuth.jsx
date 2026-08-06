import { Navigate, Outlet, useLocation } from 'react-router-dom'
import useAuth from '../../hooks/useAuth'

/**
 * The client-side half of the role gate.
 *
 * **It is not a security boundary and must not be mistaken for one.** Every route on the API is
 * guarded server-side; this only decides what to render. Somebody who edits their stored
 * principal to say `university` gets a university-shaped shell whose every request comes back
 * 403, because the token they hold is unchanged and the server reads the token.
 *
 * What it is for is the ordinary case: not showing a student a page of buttons that will all
 * fail, and sending an unauthenticated visitor to the login form with `from` set so they land
 * where they were going.
 */
export default function RequireAuth({ allowedRoles }) {
  const { role, isSignedIn } = useAuth()
  const location = useLocation()

  if (!isSignedIn) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (allowedRoles && !allowedRoles.includes(role)) {
    return <Navigate to="/unauthorized" replace />
  }

  return <Outlet />
}
