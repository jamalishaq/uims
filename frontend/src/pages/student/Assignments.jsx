import { useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { createColumnHelper } from '@tanstack/react-table'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import { useAssignments, useSubmitAssignment } from '../../features/assignments/queries'
import { useMyEnrollments } from '../../features/enrollment/queries'

const col = createColumnHelper()

function formatDate(dateStr) {
  if (!dateStr) return '—'
  try {
    return new Date(dateStr).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function isLate(dueDate, submittedAt) {
  if (!dueDate || !submittedAt) return false
  return new Date(submittedAt) > new Date(dueDate)
}

export default function Assignments() {
  useTitle('My Assignments')

  // Get enrolled sections to use as a filter if needed
  const { data: enrollments = [] } = useMyEnrollments()

  // Extract section ids from enrollments
  const sectionIds = enrollments.map((e) => e.section_id ?? e.section?.id).filter(Boolean)

  // Fetch assignments - if many sections, we fetch without filter; API should return student-scoped results
  const { data: assignments = [], isLoading } = useAssignments()

  const { mutate: submitAssignment, isPending: submitting } = useSubmitAssignment()

  const [submitModal, setSubmitModal] = useState(null) // assignment object
  const [fileUrl, setFileUrl] = useState('')

  const openSubmit = (assignment) => {
    setSubmitModal(assignment)
    setFileUrl('')
  }

  const handleSubmit = () => {
    if (!fileUrl.trim()) {
      toast.error('Please enter a file URL.')
      return
    }
    submitAssignment(
      { id: submitModal.id, file_url: fileUrl.trim() },
      {
        onSuccess: () => {
          toast.success('Assignment submitted successfully.')
          setSubmitModal(null)
          setFileUrl('')
        },
        onError: (err) => {
          const msg = err?.response?.data?.detail || err?.message || 'Submission failed.'
          toast.error(msg)
        },
      }
    )
  }

  const columns = useMemo(
    () => [
      col.accessor((row) => row.title ?? '—', {
        id: 'title',
        header: 'Assignment Title',
      }),
      col.accessor(
        (row) =>
          row.section?.course?.code ??
          row.course_code ??
          row.section?.course?.title ??
          row.course_title ??
          '—',
        {
          id: 'course',
          header: 'Course',
        }
      ),
      col.display({
        id: 'due_date',
        header: 'Due Date',
        cell: ({ row }) => formatDate(row.original.due_date),
      }),
      col.display({
        id: 'late',
        header: 'Late?',
        cell: ({ row }) => {
          const a = row.original
          const submission = a.my_submission ?? a.submission
          if (!submission) return <span className="text-slate-400 dark:text-slate-500 text-xs">—</span>
          const late = isLate(a.due_date, submission.submitted_at ?? submission.created_at)
          return late ? (
            <Badge color="danger">Late</Badge>
          ) : (
            <Badge color="success">On Time</Badge>
          )
        },
      }),
      col.display({
        id: 'submitted',
        header: 'Submitted?',
        cell: ({ row }) => {
          const a = row.original
          const submission = a.my_submission ?? a.submission
          return submission ? (
            <Badge color="success">Yes</Badge>
          ) : (
            <Badge color="warning">No</Badge>
          )
        },
      }),
      col.display({
        id: 'score',
        header: 'Score',
        cell: ({ row }) => {
          const a = row.original
          const submission = a.my_submission ?? a.submission
          if (!submission) return '—'
          return submission.score ?? submission.grade ?? '—'
        },
      }),
      col.display({
        id: 'action',
        header: '',
        cell: ({ row }) => {
          const a = row.original
          const submission = a.my_submission ?? a.submission
          if (submission) return null
          return (
            <Button size="sm" variant="primary" onClick={() => openSubmit(a)}>
              Submit
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
        title="My Assignments"
        subtitle="View and submit your course assignments."
      />

      <Table
        columns={columns}
        data={assignments}
        isLoading={isLoading}
        emptyMessage="No assignments found."
      />

      <Modal
        open={!!submitModal}
        onClose={() => setSubmitModal(null)}
        title={`Submit: ${submitModal?.title ?? 'Assignment'}`}
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              File URL
            </label>
            <input
              type="url"
              value={fileUrl}
              onChange={(e) => setFileUrl(e.target.value)}
              placeholder="https://drive.google.com/..."
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
              Paste a Google Drive, OneDrive, or any publicly accessible file link.
            </p>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setSubmitModal(null)}>
              Cancel
            </Button>
            <Button variant="primary" loading={submitting} onClick={handleSubmit}>
              Submit Assignment
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
