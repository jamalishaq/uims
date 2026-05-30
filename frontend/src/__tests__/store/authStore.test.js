import useAuthStore from '../../../store/authStore'

vi.mock('jwt-decode', () => ({
  jwtDecode: vi.fn(),
}))

import { jwtDecode } from 'jwt-decode'

const makeToken = (payload) => {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.fakesig`
}

beforeEach(() => {
  useAuthStore.setState({ token: null, rememberMe: false })
  vi.clearAllMocks()
})

describe('authStore', () => {
  it('initial state has null token', () => {
    const { token } = useAuthStore.getState()
    expect(token).toBeNull()
  })

  it('setToken stores the token', () => {
    const token = makeToken({ username: 'alice', role: 'student' })
    useAuthStore.getState().setToken(token)
    expect(useAuthStore.getState().token).toBe(token)
  })

  it('clearAuth removes the token', () => {
    const token = makeToken({ username: 'alice', role: 'student' })
    useAuthStore.getState().setToken(token)
    expect(useAuthStore.getState().token).toBe(token)

    useAuthStore.getState().clearAuth()
    expect(useAuthStore.getState().token).toBeNull()
  })

  it('getUser returns null when no token', () => {
    const user = useAuthStore.getState().getUser()
    expect(user).toBeNull()
  })

  it('getUser decodes token when present', () => {
    const payload = { username: 'bob', role: 'lecturer', user_id: 99 }
    const token = makeToken(payload)
    jwtDecode.mockReturnValue(payload)

    useAuthStore.getState().setToken(token)
    const user = useAuthStore.getState().getUser()

    expect(user).toEqual(payload)
    expect(jwtDecode).toHaveBeenCalledWith(token)
  })

  it('setRememberMe updates flag', () => {
    expect(useAuthStore.getState().rememberMe).toBe(false)
    useAuthStore.getState().setRememberMe(true)
    expect(useAuthStore.getState().rememberMe).toBe(true)
    useAuthStore.getState().setRememberMe(false)
    expect(useAuthStore.getState().rememberMe).toBe(false)
  })
})
