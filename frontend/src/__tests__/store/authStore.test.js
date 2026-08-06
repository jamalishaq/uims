import useAuthStore from '../../store/authStore'

/**
 * The session store, after the token stopped being something this app parses.
 *
 * The suite this replaces mocked `jwt-decode` and asserted that `getUser()` decoded the token.
 * That whole design is gone: `/auth/login` and `/auth/refresh` return the principal in the body,
 * so the token is opaque here — something to put in a header. Mocking a JWT library to test a
 * store that no longer uses one was testing the mock.
 */
const session = (overrides = {}) => ({
  access_token: 'header.body.signature',
  principal: {
    principal_id: 'dept-csc',
    login_id: 'dept-csc',
    role: 'department',
    scope_kind: 'department',
    scope_id: 'dept-csc',
    is_active: true,
    ...overrides,
  },
})

beforeEach(() => {
  useAuthStore.setState({ accessToken: null, principal: null })
})

describe('authStore', () => {
  it('starts with no session', () => {
    expect(useAuthStore.getState().accessToken).toBeNull()
    expect(useAuthStore.getState().principal).toBeNull()
  })

  it('signIn installs the token and the principal the server sent', () => {
    useAuthStore.getState().signIn(session())
    expect(useAuthStore.getState().accessToken).toBe('header.body.signature')
    expect(useAuthStore.getState().principal.role).toBe('department')
    expect(useAuthStore.getState().principal.scope_id).toBe('dept-csc')
  })

  it('signOut clears both halves', () => {
    useAuthStore.getState().signIn(session())
    useAuthStore.getState().signOut()
    expect(useAuthStore.getState().accessToken).toBeNull()
    expect(useAuthStore.getState().principal).toBeNull()
  })

  it('a refresh that omits the principal keeps the one already held', () => {
    // `/auth/refresh` re-reads the credential and normally returns it, but a response without
    // one must not blank the session — the token is still good.
    useAuthStore.getState().signIn(session())
    useAuthStore.getState().signIn({ access_token: 'a.newer.token' })

    expect(useAuthStore.getState().accessToken).toBe('a.newer.token')
    expect(useAuthStore.getState().principal.login_id).toBe('dept-csc')
  })

  it('a refresh that returns a changed principal replaces it', () => {
    // The server re-reads the credential on refresh, so a role or scope changed since login
    // arrives here. Keeping the stale one would render the wrong shell for up to twelve hours.
    useAuthStore.getState().signIn(session())
    useAuthStore.getState().signIn(session({ role: 'university', scope_id: 'uni-lasu' }))

    expect(useAuthStore.getState().principal.role).toBe('university')
    expect(useAuthStore.getState().principal.scope_id).toBe('uni-lasu')
  })

  it('never persists the access token', () => {
    // The refresh cookie restores a session through a value this code cannot read, so keeping a
    // bearer token in localStorage buys nothing and is the first thing an XSS writeup reaches
    // for. Only the principal survives a reload.
    useAuthStore.getState().signIn(session())
    const stored = JSON.parse(localStorage.getItem('ums.theme') ?? 'null')
    expect(stored?.state?.accessToken).toBeUndefined()

    const persisted = JSON.parse(localStorage.getItem('ums.session') ?? '{}')
    expect(persisted.state?.accessToken).toBeUndefined()
    expect(persisted.state?.principal?.login_id).toBe('dept-csc')
  })
})
