import { useMemo } from 'react'
import toast from 'react-hot-toast'
import { createColumnHelper } from '@tanstack/react-table'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import { useSections } from '../../features/courses/queries'
import { useEnroll } from '../../features/enrollment/queries'

const col = createColumnHelper()

export default function Courses() {
  useTitle('Browse Courses')

  const { data: sections = [], isLoading } = useSections()
  const { mutate: enroll, isPending } = useEnroll()

  const handleEnroll = (section) => {
    enroll(
      { section_id: section.id },
      {
        onSuccess: () => toast.success(`Enrolled in ${section.course_code ?? section.course?.code ?? 'course'}`),
        onError: (err) => {
          const msg =
            err?.response?.data?.detail ||
            err?.response?.data?.message ||
            err?.message ||
            'Enrollment failed'
          toast.error(msg)
        },
      }
    )
  }

  const columns = useMemo(
    () => [
      col.accessor((row) => row.course?.code ?? row.course_code ?? '—', {
        id: 'code',
        header: 'Course Code',
      }),
      col.accessor((row) => row.course?.title ?? row.title ?? '—', {
        id: 'title',
        header: 'Title',
      }),
      col.accessor((row) => row.course?.credit_hours ?? row.credit_hours ?? '—', {
        id: 'credits',
        header: 'Credits',
      }),
      col.accessor((row) => row.lecturer?.name ?? row.lecturer_name ?? '—', {
        id: 'lecturer',
        header: 'Lecturer',
      }),
      col.accessor((row) => row.schedule ?? '—', {
        id: 'schedule',
        header: 'Schedule',
      }),
      col.accessor((row) => row.venue ?? '—', {
        id: 'venue',
        header: 'Venue',
      }),
      col.display({
        id: 'spots',
        header: 'Spots',
        cell: ({ row }) => {
          const s = row.original
          const enrolled = s.enrolled_count ?? s.enrolled ?? 0
          const max = s.max_students ?? s.capacity ?? '?'
          const full = typeof max === 'number' && enrolled >= max
          return (
            <Badge color={full ? 'danger' : 'success'}>
              {enrolled}/{max}
            </Badge>
          )
        },
      }),
      col.display({
        id: 'action',
        header: '',
        cell: ({ row }) => {
          const s = row.original
          const enrolled = s.enrolled_count ?? s.enrolled ?? 0
          const max = s.max_students ?? s.capacity
          const full = typeof max === 'number' && enrolled >= max
          return (
            <Button
              size="sm"
              variant="primary"
              disabled={full || isPending}
              onClick={() => handleEnroll(s)}
            >
              {full ? 'Full' : 'Enroll'}
            </Button>
          )
        },
      }),
    ],
    [isPending] // eslint-disable-line react-hooks/exhaustive-deps
  )

  return (
    <div>
      <PageHeader
        title="Browse Courses"
        subtitle="View available course sections and enroll for this semester."
      />
      <Table columns={columns} data={sections} isLoading={isLoading} emptyMessage="No course sections available." />
    </div>
  )
}
