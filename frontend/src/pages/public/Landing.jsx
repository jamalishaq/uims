import { Navigate } from 'react-router-dom'
import useAuth from '../../hooks/useAuth'
import { ROLE_HOME } from '../../config/roles'

/**
 * The root path, which belongs to whoever is signed in.
 *
 * A remembered principal goes straight to its own home; everybody else to the login form. The
 * previous version redirected unconditionally to `/login`, which bounced a signed-in user
 * through the login page on every visit to `/`.
 */
export default function Landing() {
  const { isSignedIn, role } = useAuth()
  return <Navigate to={isSignedIn && role ? (ROLE_HOME[role] ?? '/login') : '/login'} replace />
}
