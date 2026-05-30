import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table, { createColumnHelper } from '../../components/ui/Table'
import Button from '../../components/ui/Button'
import { useSections } from '../../features/courses/queries'

const col = createColumnHelper()

export default function Sections() {
  useTitle('My Sections')
  const { sub: user_id } = useAuth()
  const navigate = useNavigate()

  const { data: sections = [], isLoading } = useSections(
    user_id ? { lecturer_id: user_id } : undefined,
  )

  const columns = useMemo(
    () => [
      col.accessor('course_code', { header: 'Course Code' }),
      col.accessor('course_title', { header: 'Title' }),
      col.accessor('semester', { header: 'Semester' }),
      col.accessor('schedule', { header: 'Schedule' }),
      col.accessor('venue', { header: 'Venue' }),
      col.accessor('enrolled_count', {
        header: 'Enrolled',
        cell: (info) => (
          <span className="font-medium text-indigo-600 dark:text-indigo-400">
            {info.getValue() ?? '—'}
          </span>
        ),
      }),
      col.display({
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => {
          const id = row.original.id
          return (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => navigate(`/lecturer/attendance?section=${id}`)}
              >
                Attendance
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => navigate(`/lecturer/assignments?section=${id}`)}
              >
                Assignments
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => navigate(`/lecturer/grades?section=${id}`)}
              >
                Grades
              </Button>
            </div>
          )
        },
      }),
    ],
    [navigate],
  )

  return (
    <div>
      <PageHeader
        title="My Course Sections"
        subtitle="All sections assigned to you this semester."
      />
      <Table
        columns={columns}
        data={sections}
        isLoading={isLoading}
        emptyMessage="No sections found for your account."
      />
    </div>
  )
}
