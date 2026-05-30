import { renderHook } from '@testing-library/react'
import { act } from 'react'
import useAuth from '../../hooks/useAuth'
import useAuthStore from '../../store/authStore'

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

describe('useAuth', () => {
  it('returns empty object when no token', () => {
    const { result } = renderHook(() => useAuth())
    expect(result.current).toEqual({})
  })

  it('decodes JWT and returns payload', () => {
    const payload = { username: 'alice', role: 'student', user_id: 1 }
    const token = makeToken(payload)
    jwtDecode.mockReturnValue(payload)

    act(() => {
      useAuthStore.setState({ token })
    })

    const { result } = renderHook(() => useAuth())
    expect(result.current).toEqual(payload)
    expect(jwtDecode).toHaveBeenCalledWith(token)
  })

  it('returns username and role from token', () => {
    const payload = { username: 'testuser', role: 'student', user_id: 42 }
    const token = makeToken(payload)
    jwtDecode.mockReturnValue(payload)

    act(() => {
      useAuthStore.setState({ token })
    })

    const { result } = renderHook(() => useAuth())
    expect(result.current.username).toBe('testuser')
    expect(result.current.role).toBe('student')
  })

  it('updates when token changes', () => {
    const firstPayload = { username: 'alice', role: 'student' }
    const secondPayload = { username: 'bob', role: 'lecturer' }
    const firstToken = makeToken(firstPayload)
    const secondToken = makeToken(secondPayload)

    jwtDecode.mockReturnValueOnce(firstPayload).mockReturnValueOnce(secondPayload)

    act(() => {
      useAuthStore.setState({ token: firstToken })
    })

    const { result } = renderHook(() => useAuth())
    expect(result.current.username).toBe('alice')

    act(() => {
      useAuthStore.setState({ token: secondToken })
    })

    expect(result.current.username).toBe('bob')
  })

  it('returns empty object for invalid token', () => {
    jwtDecode.mockImplementation(() => {
      throw new Error('Invalid token')
    })

    act(() => {
      useAuthStore.setState({ token: 'not.a.valid.jwt' })
    })

    const { result } = renderHook(() => useAuth())
    expect(result.current).toEqual({})
  })
})
