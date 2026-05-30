import { render, screen, waitFor, fireEvent } from '../../test-utils'
import userEvent from '@testing-library/user-event'
import Login from '../../pages/public/Login'
import useAuthStore from '../../store/authStore'

// Mock the login mutation function
vi.mock('../../features/auth/queries', () => ({
  login: vi.fn(),
}))

// Mock jwt-decode used inside Login on success
vi.mock('jwt-decode', () => ({
  jwtDecode: vi.fn(() => ({ role: 'student' })),
}))

// Mock react-hot-toast so we can spy on it
vi.mock('react-hot-toast', () => ({
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

import { login } from '../../features/auth/queries'
import toast from 'react-hot-toast'

beforeEach(() => {
  useAuthStore.setState({ token: null, rememberMe: false })
  vi.clearAllMocks()
})

describe('Login', () => {
  it('renders email and password fields', () => {
    render(<Login />)
    expect(screen.getByPlaceholderText(/you@university\.edu/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/••••••••/)).toBeInTheDocument()
  })

  it('renders sign in button', () => {
    render(<Login />)
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument()
  })

  it('shows validation error for empty email', async () => {
    const user = userEvent.setup()
    render(<Login />)

    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText(/enter a valid email/i)).toBeInTheDocument()
    })
  })

  it('shows validation error for invalid email format', async () => {
    render(<Login />)

    fireEvent.change(screen.getByPlaceholderText(/you@university\.edu/i), {
      target: { value: 'notanemail' },
    })
    fireEvent.submit(document.querySelector('form'))

    await waitFor(() => {
      expect(screen.getByText(/enter a valid email/i)).toBeInTheDocument()
    })
  })

  it('shows validation error for empty password', async () => {
    const user = userEvent.setup()
    render(<Login />)

    await user.type(screen.getByPlaceholderText(/you@university\.edu/i), 'user@example.com')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(screen.getByText(/password is required/i)).toBeInTheDocument()
    })
  })

  it('calls login mutation on valid submit', async () => {
    login.mockReturnValue(new Promise(() => {}))

    render(<Login />)

    fireEvent.change(screen.getByPlaceholderText(/you@university\.edu/i), {
      target: { value: 'student@university.edu' },
    })
    fireEvent.change(screen.getByPlaceholderText(/••••••••/), {
      target: { value: 'secret123' },
    })
    fireEvent.submit(document.querySelector('form'))

    await waitFor(() => expect(login).toHaveBeenCalled())
    expect(login.mock.calls[0][0]).toMatchObject({
      email: 'student@university.edu',
      password: 'secret123',
    })
  })

  it('shows error toast on login failure', async () => {
    const user = userEvent.setup()
    login.mockRejectedValue(new Error('Unauthorized'))

    render(<Login />)

    await user.type(screen.getByPlaceholderText(/you@university\.edu/i), 'bad@example.com')
    await user.type(screen.getByPlaceholderText(/••••••••/), 'wrongpass')
    await user.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Invalid email or password')
    })
  })
})
