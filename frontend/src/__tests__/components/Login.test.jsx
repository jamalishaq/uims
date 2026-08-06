import { render, screen, waitFor } from '../../test-utils'
import userEvent from '@testing-library/user-event'
import Login from '../../pages/public/Login'
import useAuthStore from '../../store/authStore'
import api from '../../lib/api'

/**
 * The login form, against the real `/auth/login` contract.
 *
 * The suite this replaces mocked `jwt-decode` — the form no longer decodes anything, because
 * the server returns the principal in the body. What is worth testing here is the contract:
 * the request shape, the session that results, and that a refusal shows the server's message
 * rather than one this app invented.
 */
vi.mock('../../lib/api', async () => {
  const actual = await vi.importActual('../../lib/api')
  return {
    ...actual,
    default: { post: vi.fn(), get: vi.fn(), interceptors: { request: {}, response: {} } },
  }
})

const session = {
  access_token: 'header.body.signature',
  token_type: 'bearer',
  expires_in_seconds: 1800,
  principal: {
    principal_id: 'stu-1',
    login_id: '260591001',
    role: 'student',
    scope_kind: 'student',
    scope_id: 'stu-1',
    is_active: true,
  },
}

beforeEach(() => {
  useAuthStore.setState({ accessToken: null, principal: null })
  vi.clearAllMocks()
})

describe('Login', () => {
  it('renders one field for every kind of principal', () => {
    render(<Login />)
    // One field, no role picker: the server decides what a login id is, and choosing a role
    // first would let somebody pick wrong and be told their correct password was invalid.
    expect(screen.getByLabelText(/matric number or id/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/role/i)).not.toBeInTheDocument()
  })

  it('sends the login id and password in the shape the API declares', async () => {
    api.post.mockResolvedValue({ data: session })
    const user = userEvent.setup()

    render(<Login />)
    await user.type(screen.getByLabelText(/matric number or id/i), '260591001')
    await user.type(screen.getByLabelText(/password/i), 'a-real-password')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/auth/login', {
        login_id: '260591001',
        password: 'a-real-password',
      })
    )
  })

  it('installs the session the server returned', async () => {
    api.post.mockResolvedValue({ data: session })
    const user = userEvent.setup()

    render(<Login />)
    await user.type(screen.getByLabelText(/matric number or id/i), '260591001')
    await user.type(screen.getByLabelText(/password/i), 'a-real-password')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => expect(useAuthStore.getState().accessToken).toBe(session.access_token))
    expect(useAuthStore.getState().principal.role).toBe('student')
  })

  it('trims the login id but never the password', async () => {
    // A leading space in a password is a character the person typed and will type again;
    // stripping it would silently send a different password from the one they entered.
    api.post.mockResolvedValue({ data: session })
    const user = userEvent.setup()

    render(<Login />)
    await user.type(screen.getByLabelText(/matric number or id/i), '  260591001  ')
    await user.type(screen.getByLabelText(/password/i), ' spaced ')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith('/auth/login', {
        login_id: '260591001',
        password: ' spaced ',
      })
    )
  })

  it("shows the server's refusal rather than one of its own", async () => {
    api.post.mockRejectedValue({
      response: { status: 401, data: { error: 'AuthenticationFailedError', detail: 'login id or password is incorrect' } },
    })
    const user = userEvent.setup()

    render(<Login />)
    await user.type(screen.getByLabelText(/matric number or id/i), 'nobody')
    await user.type(screen.getByLabelText(/password/i), 'wrong')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByText(/login id or password is incorrect/i)).toBeInTheDocument()
    expect(useAuthStore.getState().accessToken).toBeNull()
  })
})
