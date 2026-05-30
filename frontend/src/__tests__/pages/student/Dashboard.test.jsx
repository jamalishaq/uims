import { render, screen, waitFor } from '../../../test-utils'
import { act } from 'react'
import StudentDashboard from '../../../../pages/student/Dashboard'
import useAuthStore from '../../../../store/authStore'

vi.mock('../../../../features/enrollment/queries', () => ({
  useMyEnrollments: vi.fn(),
}))

vi.mock('../../../../features/students/queries', () => ({
  useMyStudentRecord: vi.fn(),
}))

vi.mock('../../../../features/grades/queries', () => ({
  useTranscript: vi.fn(),
}))

vi.mock('jwt-decode', () => ({
  jwtDecode: vi.fn(),
}))

import { useMyEnrollments } from '../../../../features/enrollment/queries'
import { useMyStudentRecord } from '../../../../features/students/queries'
import { useTranscript } from '../../../../features/grades/queries'
import { jwtDecode } from 'jwt-decode'

const makeToken = (payload) => {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.fakesig`
}

beforeEach(() => {
  useAuthStore.setState({ token: null, rememberMe: false })
  vi.clearAllMocks()

  // Default: all queries return empty / idle state
  useMyEnrollments.mockReturnValue({ data: [], isLoading: false })
  useMyStudentRecord.mockReturnValue({ data: undefined, isLoading: false })
  useTranscript.mockReturnValue({ data: undefined, isLoading: false })
})

describe('StudentDashboard', () => {
  it('renders welcome message with username from auth', () => {
    const payload = { username: 'testuser', role: 'student', user_id: 1 }
    const token = makeToken(payload)
    jwtDecode.mockReturnValue(payload)

    act(() => {
      useAuthStore.setState({ token })
    })

    render(<StudentDashboard />)

    expect(screen.getByText(/welcome, testuser/i)).toBeInTheDocument()
  })

  it('renders four stat cards', () => {
    render(<StudentDashboard />)

    expect(screen.getByText('Enrolled Courses')).toBeInTheDocument()
    expect(screen.getByText('Credit Hours')).toBeInTheDocument()
    expect(screen.getByText('CGPA')).toBeInTheDocument()
    expect(screen.getByText('Credits Passed')).toBeInTheDocument()
  })

  it('shows loading state in stat cards', () => {
    useMyEnrollments.mockReturnValue({ data: [], isLoading: true })
    useMyStudentRecord.mockReturnValue({ data: undefined, isLoading: true })
    useTranscript.mockReturnValue({ data: undefined, isLoading: true })

    render(<StudentDashboard />)

    // Loading indicators are shown as '...' for each stat
    const loadingIndicators = screen.getAllByText('...')
    expect(loadingIndicators.length).toBeGreaterThan(0)
  })

  it('shows real data in stat cards', async () => {
    const enrollments = [
      { id: 1, section: { course: { credit_hours: 3 } }, status: 'enrolled' },
      { id: 2, section: { course: { credit_hours: 4 } }, status: 'enrolled' },
    ]
    const studentRecord = { id: 10 }
    const transcript = { cgpa: '3.75', total_credits_passed: 60 }

    useMyEnrollments.mockReturnValue({ data: enrollments, isLoading: false })
    useMyStudentRecord.mockReturnValue({ data: studentRecord, isLoading: false })
    useTranscript.mockReturnValue({ data: transcript, isLoading: false })

    render(<StudentDashboard />)

    await waitFor(() => {
      // 2 enrolled courses
      expect(screen.getByText('2')).toBeInTheDocument()
      // 7 total credit hours (3+4)
      expect(screen.getByText('7')).toBeInTheDocument()
      // CGPA formatted
      expect(screen.getByText('3.75')).toBeInTheDocument()
      // Credits passed
      expect(screen.getByText('60')).toBeInTheDocument()
    })
  })
})
