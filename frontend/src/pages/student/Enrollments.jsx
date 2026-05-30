import { useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { createColumnHelper } from '@tanstack/react-table'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import Card, { CardBody } from '../../components/ui/Card'
import { useMyEnrollments, useDropCourse } from '../../features/enrollment/queries'

const col = createColumnHelper()

function statusColor(status) {
  if (!status) return 'default'
  const s = status.toLowerCase()
  if (s === 'enrolled' || s === 'active') return 'indigo'
  if (s === 'dropped') return 'danger'
  if (s === 'completed') return 'success'
  return 'default'
}

export default function Enrollments() {
  useTitle('My Enrollments')

  const { data: enrollments = [], isLoading } = useMyEnrollments()
  const { mutate: drop, isPending: dropping } = useDropCourse()

  const [confirmId, setConfirmId] = useState(null)
  const confirmItem = enrollments.find((e) => e.id === confirmId)

  const totalCredits = enrollments.reduce((sum, e) => {
    const ch = e.section?.course?.credit_hours ?? e.credit_hours ?? 0
    return sum + Number(ch)
  }, 0)

  const handleDrop = () => {
    drop(confirmId, {
      onSuccess: () => {
        toast.success('Course dropped successfully.')
        setConfirmId(null)
      },
      onError: (err) => {
        const msg = err?.response?.data?.detail || err?.message || 'Failed to drop course.'
        toast.error(msg)
      },
    })
  }

  const columns = useMemo(
    () => [
      col.accessor((row) => row.section?.course?.code ?? row.course_code ?? '—', {
        id: 'code',
        header: 'Course Code',
      }),
      col.accessor((row) => row.section?.course?.title ?? row.course_title ?? '—', {
        id: 'title',
        header: 'Title',
      }),
      col.accessor((row) => row.section?.course?.credit_hours ?? row.credit_hours ?? '—', {
        id: 'credits',
        header: 'Credits',
      }),
      col.accessor((row) => row.section?.schedule ?? row.schedule ?? '—', {
        id: 'schedule',
        header: 'Schedule',
      }),
      col.accessor((row) => row.grade ?? '—', {
        id: 'grade',
        header: 'Grade',
      }),
      col.display({
        id: 'status',
        header: 'Status',
        cell: ({ row }) => {
          const status = row.original.status ?? 'Enrolled'
          return <Badge color={statusColor(status)}>{status}</Badge>
        },
      }),
      col.display({
        id: 'action',
        header: '',
        cell: ({ row }) => {
          const e = row.original
          const isDroopable = !e.status || ['enrolled', 'active'].includes((e.status ?? '').toLowerCase())
          if (!isDroopable) return null
          return (
            <Button
              size="sm"
              variant="danger"
              onClick={() => setConfirmId(e.id)}
            >
              Drop
            </Button>
          )
        },
      }),
    ],
    []
  )

  return (
    <div>
      <PageHeader
        title="My Enrollments"
        subtitle="Manage your registered courses for this semester."
      />

      <div className="mb-4">
        <Card>
          <CardBody className="py-3">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Total Credit Hours:{' '}
              <span className="font-semibold text-slate-900 dark:text-slate-100">{totalCredits}</span>
            </p>
          </CardBody>
        </Card>
      </div>

      <Table
        columns={columns}
        data={enrollments}
        isLoading={isLoading}
        emptyMessage="You are not enrolled in any courses yet."
      />

      <Modal
        open={!!confirmId}
        onClose={() => setConfirmId(null)}
        title="Drop Course"
      >
        <p className="text-sm text-slate-600 dark:text-slate-300 mb-6">
          Are you sure you want to drop{' '}
          <strong>
            {confirmItem?.section?.course?.code ?? confirmItem?.course_code ?? 'this course'}
          </strong>
          ? This action cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setConfirmId(null)}>
            Cancel
          </Button>
          <Button variant="danger" loading={dropping} onClick={handleDrop}>
            Drop Course
          </Button>
        </div>
      </Modal>
    </div>
  )
}
