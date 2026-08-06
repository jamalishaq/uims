import { renderHook } from '../../test-utils'
import useAuth from '../../hooks/useAuth'
import useAuthStore from '../../store/authStore'

/**
 * `useAuth` reads the stored principal. It no longer decodes anything.
 *
 * `scopeId` is the field worth testing: pages use it to fill in the path parameter the API
 * expects, which is why a student's transcript is fetched from `/records/{scopeId}` and not from
 * a `/records/me` route that does not exist.
 */
const principal = (overrides = {}) => ({
  principal_id: 'stu-1',
  login_id: '260591001',
  role: 'student',
  scope_kind: 'student',
  scope_id: 'stu-1',
  is_active: true,
  ...overrides,
})

beforeEach(() => {
  useAuthStore.setState({ accessToken: null, principal: null })
})

describe('useAuth', () => {
  it('reports nobody signed in when there is no principal', () => {
    const { result } = renderHook(() => useAuth())
    expect(result.current.isSignedIn).toBe(false)
    expect(result.current.role).toBeNull()
    expect(result.current.scopeId).toBeNull()
  })

  it('exposes the principal the server sent', () => {
    useAuthStore.setState({ accessToken: 'a.b.c', principal: principal() })
    const { result } = renderHook(() => useAuth())

    expect(result.current.isSignedIn).toBe(true)
    expect(result.current.role).toBe('student')
    expect(result.current.principalId).toBe('stu-1')
    expect(result.current.scopeId).toBe('stu-1')
  })

  it('keeps the login id separate from the principal id', () => {
    // For a student these genuinely differ — the login id is their matric number and the
    // principal id is what Student Profile minted. Routes need one or the other depending on
    // which context keys the record, so conflating them would break half of them.
    useAuthStore.setState({ accessToken: 'a.b.c', principal: principal() })
    const { result } = renderHook(() => useAuth())

    expect(result.current.loginId).toBe('260591001')
    expect(result.current.principalId).toBe('stu-1')
  })

  it('reports a principal with no token as signed in but tokenless', () => {
    // What a reload looks like before PersistLogin's refresh lands: the principal is persisted,
    // the access token never is.
    useAuthStore.setState({ accessToken: null, principal: principal() })
    const { result } = renderHook(() => useAuth())

    expect(result.current.isSignedIn).toBe(true)
    expect(result.current.hasToken).toBe(false)
  })
})
