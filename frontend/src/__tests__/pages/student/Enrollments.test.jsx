import { render, screen, waitFor, fireEvent } from '../../../test-utils'
import Enrollments from '../../../../pages/student/Enrollments'

vi.mock('../../../../features/enrollment/queries', () => ({
  useMyEnrollments: vi.fn(),
  useDropCourse: vi.fn(),
}))

// Mock react-hot-toast
vi.mock('react-hot-toast', () => ({
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}))

import { useMyEnrollments, useDropCourse } from '../../../../features/enrollment/queries'

const mockDropMutate = vi.fn()

const sampleEnrollments = [
  {
    id: 1,
    status: 'enrolled',
    section: {
      course: { code: 'CS101', title: 'Intro to CS', credit_hours: 3 },
      schedule: 'Mon/Wed 9-10am',
    },
    grade: null,
  },
  {
    id: 2,
    status: 'enrolled',
    section: {
      course: { code: 'MATH201', title: 'Calculus II', credit_hours: 4 },
      schedule: 'Tue/Thu 11-12pm',
    },
    grade: null,
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  useDropCourse.mockReturnValue({ mutate: mockDropMutate, isPending: false })
})

describe('Enrollments', () => {
  it('shows loading skeleton', () => {
    useMyEnrollments.mockReturnValue({ data: [], isLoading: true })
    render(<Enrollments />)

    // When loading, skeleton rows with animate-pulse are rendered
    const skeletons = document.querySelectorAll('.animate-pulse')
    expect(skeletons.length).toBeGreaterThan(0)
  })

  it('renders enrollment table when data loads', async () => {
    useMyEnrollments.mockReturnValue({ data: sampleEnrollments, isLoading: false })
    render(<Enrollments />)

    await waitFor(() => {
      expect(screen.getByText('Course Code')).toBeInTheDocument()
      expect(screen.getByText('Title')).toBeInTheDocument()
      expect(screen.getByText('Credits')).toBeInTheDocument()
      expect(screen.getByText('CS101')).toBeInTheDocument()
      expect(screen.getByText('Intro to CS')).toBeInTheDocument()
      expect(screen.getByText('MATH201')).toBeInTheDocument()
      expect(screen.getByText('Calculus II')).toBeInTheDocument()
    })
  })

  it('shows empty state when no enrollments', () => {
    useMyEnrollments.mockReturnValue({ data: [], isLoading: false })
    render(<Enrollments />)

    expect(
      screen.getByText('You are not enrolled in any courses yet.')
    ).toBeInTheDocument()
  })

  it('shows credit hour total', async () => {
    useMyEnrollments.mockReturnValue({ data: sampleEnrollments, isLoading: false })
    render(<Enrollments />)

    await waitFor(() => {
      // The card contains "Total Credit Hours: 7"
      expect(screen.getByText(/total credit hours/i)).toBeInTheDocument()
      // The credit sum (3+4=7) appears as a separate span
      expect(screen.getByText('7')).toBeInTheDocument()
    })
  })

  it('shows Drop button for each enrollment', async () => {
    useMyEnrollments.mockReturnValue({ data: sampleEnrollments, isLoading: false })
    render(<Enrollments />)

    await waitFor(() => {
      const dropButtons = screen.getAllByRole('button', { name: /drop/i })
      // Each droppable enrollment has a Drop button
      expect(dropButtons.length).toBeGreaterThanOrEqual(sampleEnrollments.length)
    })
  })

  it('opens confirmation modal on Drop click', async () => {
    useMyEnrollments.mockReturnValue({ data: sampleEnrollments, isLoading: false })
    render(<Enrollments />)

    await waitFor(() => {
      expect(screen.getByText('CS101')).toBeInTheDocument()
    })

    // Click the first Drop button
    const dropButtons = screen.getAllByRole('button', { name: /^drop$/i })
    fireEvent.click(dropButtons[0])

    await waitFor(() => {
      expect(screen.getByText('Drop Course')).toBeInTheDocument()
      expect(screen.getByText(/are you sure you want to drop/i)).toBeInTheDocument()
    })
  })
})
