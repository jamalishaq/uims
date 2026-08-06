import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'
import useAuthStore from '../../store/authStore'

/**
 * The login surface: `/auth/*` on the API.
 *
 * Every function here maps to a route that exists. That was not true of the file this replaces.
 */

export const useSignIn = () => {
  const signIn = useAuthStore((s) => s.signIn)
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ loginId, password }) =>
      api.post('/auth/login', { login_id: loginId, password }).then((r) => r.data),
    onSuccess: (session) => {
      // Clear before installing: a cache left over from the previous principal would be read
      // by the next one's first render, and a department registrar must not flash somebody
      // else's applicant list.
      queryClient.clear()
      signIn(session)
    },
  })
}

export const useSignOut = () => {
  const signOut = useAuthStore((s) => s.signOut)
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.post('/auth/logout'),
    // `onSettled`, not `onSuccess`: if the request fails the session must still end locally.
    // A logout that only works when the network does is not a logout.
    onSettled: () => {
      signOut()
      queryClient.clear()
    },
  })
}

/**
 * Who the server says this token belongs to, read back rather than taken from the token.
 *
 * The route exists to answer for a credential that has been deactivated or deleted since the
 * token was issued — an access token stays valid for up to thirty minutes either way, and
 * rendering an administrator's console for a credential that no longer exists is worse than a
 * round trip.
 */
export const useMe = (enabled = true) =>
  useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => api.get('/auth/me').then((r) => r.data),
    enabled,
    retry: false,
  })

export const useChangeMyPassword = () =>
  useMutation({
    mutationFn: ({ currentPassword, newPassword }) =>
      api
        .post('/auth/me/password', {
          current_password: currentPassword,
          new_password: newPassword,
        })
        .then((r) => r.data),
  })

// ---- university-scoped credential administration ----

export const useCredentials = () =>
  useQuery({
    queryKey: ['auth', 'credentials'],
    queryFn: () => api.get('/auth/credentials').then((r) => r.data),
  })

export const useIssueCredential = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ loginId, principalId, role, password, scopeUnitId }) =>
      api
        .post('/auth/credentials', {
          login_id: loginId,
          principal_id: principalId,
          role,
          password,
          ...(scopeUnitId ? { scope_unit_id: scopeUnitId } : {}),
        })
        .then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['auth', 'credentials'] }),
  })
}

export const useResetPassword = () =>
  useMutation({
    mutationFn: ({ loginId, newPassword }) =>
      api
        .post(`/auth/credentials/${encodeURIComponent(loginId)}/password`, {
          new_password: newPassword,
        })
        .then((r) => r.data),
  })

export const useSetCredentialActive = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ loginId, isActive }) =>
      api
        .put(`/auth/credentials/${encodeURIComponent(loginId)}/active`, { is_active: isActive })
        .then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['auth', 'credentials'] }),
  })
}
