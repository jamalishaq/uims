import axios from 'axios'
import useAuthStore from '../store/authStore'

/**
 * The one HTTP client. Every request in the app goes through it.
 *
 * `VITE_API_BASE_URL` is the origin only — `http://localhost:8000` — and the version prefix is
 * added here. The server has versioned its surface from the first release precisely so the
 * second one can move, and a base URL with `/api/v1` baked into an environment variable would
 * put that decision in a deployment's hands.
 */
export const API_PREFIX = '/api/v1'

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_BASE_URL ?? ''}${API_PREFIX}`,
  // The refresh token lives in an HttpOnly cookie the browser holds and this code cannot read.
  // Without this it would never be sent, and every session would end after thirty minutes.
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/**
 * One refresh at a time, with everything else queued behind it.
 *
 * Without the queue, a page that fires five requests on mount and gets five 401s would run five
 * refreshes. Four of them would be wasted, and — more to the point — they would race: the last
 * to land would win, and the tokens the others installed would already have been overwritten.
 */
let refreshing = null

/**
 * Requests that must never trigger a refresh, because a 401 from them *is* the answer.
 *
 * `/auth/login` answering 401 means the password was wrong. Refreshing at that point would send
 * the browser's existing cookie and, if it happened to be valid, log the user back in as
 * whoever they were before — silently ignoring the login they just attempted.
 */
const NEVER_RETRY = ['/auth/login', '/auth/refresh', '/auth/logout']

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const status = error.response?.status

    if (status !== 401 || !original || original._retried) {
      return Promise.reject(error)
    }
    if (NEVER_RETRY.some((path) => original.url?.startsWith(path))) {
      return Promise.reject(error)
    }

    original._retried = true

    refreshing ??= api
      .post('/auth/refresh')
      .then(({ data }) => {
        useAuthStore.getState().signIn(data)
        return data.access_token
      })
      .catch((failure) => {
        // The session is over: the cookie expired, or the credential was deactivated and the
        // server re-read it. Clearing here rather than redirecting — a hard `window.location`
        // would throw away an unsaved form, and the router's guard sends them to /login on the
        // next render anyway, with `from` set so they come back where they were.
        useAuthStore.getState().signOut()
        throw failure
      })
      .finally(() => {
        refreshing = null
      })

    const token = await refreshing
    original.headers.Authorization = `Bearer ${token}`
    return api(original)
  }
)

/**
 * The message the API sent, or a readable fallback.
 *
 * Every error the server produces has the same envelope — `{error, detail}` — where `error` is
 * a stable exception class name and `detail` is prose. This reads `detail`, because that is the
 * half written for a person. Callers that need to branch should key off `errorCode` instead;
 * the server's own docs say `detail` is not a stable interface.
 */
export const errorMessage = (error, fallback = 'Something went wrong.') =>
  error?.response?.data?.detail || error?.message || fallback

/** The exception class name, e.g. `QuotaExhausted`. Stable, and the thing to branch on. */
export const errorCode = (error) => error?.response?.data?.error ?? null

export default api
