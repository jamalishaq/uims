import { create } from 'zustand'
import { persist } from 'zustand/middleware'

/**
 * The session: an access token, and the principal the server said it belongs to.
 *
 * **The principal is stored, not decoded from the token.** The old store decoded the JWT with
 * `jwt-decode` on every read, which meant this app had an opinion about the server's claim
 * names and would break silently if one were renamed. `POST /auth/login` and `/auth/refresh`
 * both return the principal in the body for exactly this reason, so the token stays opaque —
 * something to put in a header, not something to parse.
 *
 * **The refresh token is not here and cannot be.** It lives in an `HttpOnly` cookie; this code
 * cannot read it, which is the whole of its protection against a script that gets onto the
 * page. Persisting it into `localStorage` would undo that in one line.
 */
const useAuthStore = create(
  persist(
    (set) => ({
      accessToken: null,
      principal: null,

      /** Install a session from a `/auth/login` or `/auth/refresh` response. */
      signIn: ({ access_token, principal }) =>
        set((state) => ({
          accessToken: access_token,
          // `/auth/refresh` returns the principal too, and it may have *changed* — the server
          // re-reads the credential rather than trusting the token. Falling back to the one we
          // hold keeps a refresh that omitted it from blanking the session.
          principal: principal ?? state.principal,
        })),

      signOut: () => set({ accessToken: null, principal: null }),
    }),
    {
      name: 'ums.session',
      /**
       * Only the principal survives a reload — never the access token.
       *
       * Keeping a bearer token in `localStorage` is the thing every XSS writeup opens with, and
       * it buys nothing here: the refresh cookie already restores the session on load, and it
       * does so through a value this code cannot read. So a reload starts with a principal to
       * render a shell from, no token, and one refresh in flight.
       */
      partialize: (state) => ({ principal: state.principal }),
    }
  )
)

export default useAuthStore
