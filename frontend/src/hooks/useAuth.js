import useAuthStore from '../store/authStore'

/**
 * Who is signed in, as the server described them.
 *
 * Reads the stored principal rather than decoding the access token — see `authStore` on why the
 * token stays opaque to this app.
 *
 * The shape mirrors `PrincipalResponse` exactly:
 *   { principalId, loginId, role, scopeKind, scopeId, isActive }
 *
 * `scopeId` is the one field worth understanding. It is the unit this principal may act on: a
 * department registrar's department id, a lecturer's own id, a student's own id. Pages use it
 * to fill in the path parameter the API expects, which is the arrangement the server asked for
 * — scope travels as an explicit parameter, and the token *constrains* it rather than replacing
 * it. That is why a student's transcript is fetched from `/records/{scopeId}` and not from a
 * `/records/me` route, which does not exist and is not going to.
 */
export default function useAuth() {
  const principal = useAuthStore((s) => s.principal)
  const accessToken = useAuthStore((s) => s.accessToken)

  if (!principal) {
    return { isSignedIn: false, role: null, scopeId: null, principalId: null, loginId: null }
  }

  return {
    isSignedIn: Boolean(principal),
    hasToken: Boolean(accessToken),
    principalId: principal.principal_id,
    loginId: principal.login_id,
    role: principal.role,
    scopeKind: principal.scope_kind,
    scopeId: principal.scope_id,
    isActive: principal.is_active,
  }
}
