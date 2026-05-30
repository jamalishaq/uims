import { useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { createColumnHelper } from '@tanstack/react-table'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import { useApplications, useDecideApplication, useEnrollApplicant } from '../../features/admission/queries'

const col = createColumnHelper()

const STATUS_TABS = [
  { label: 'All', value: '' },
  { label: 'Submitted', value: 'submitted' },
  { label: 'Screening', value: 'screening' },
  { label: 'Accepted', value: 'accepted' },
  { label: 'Rejected', value: 'rejected' },
  { label: 'Enrolled', value: 'enrolled' },
]

const STATUS_BADGE = {
  submitted: 'indigo',
  screening: 'warning',
  accepted:  'success',
  rejected:  'danger',
  enrolled:  'violet',
}

function toErrorMsg(err) {
  return (
    err?.response?.data?.detail ||
    err?.response?.data?.message ||
    err?.message ||
    'Something went wrong'
  )
}

export default function Applications() {
  useTitle('Applications')

  const [activeStatus, setActiveStatus] = useState('')
  const [rejectTarget, setRejectTarget] = useState(null) // { id, name }
  const [rejectionReason, setRejectionReason] = useState('')
  const [enrollTarget, setEnrollTarget] = useState(null) // { id, name }

  const { data: applications = [], isLoading } = useApplications(
    activeStatus ? { app_status: activeStatus } : {}
  )

  const { mutate: decide, isPending: isDeciding } = useDecideApplication()
  const { mutate: enroll, isPending: isEnrolling } = useEnrollApplicant()

  const handleAccept = (row) => {
    decide(
      { id: row.id, action: 'accept' },
      {
        onSuccess: () => toast.success(`Application for ${row.applicant_name ?? 'applicant'} accepted.`),
        onError: (err) => toast.error(toErrorMsg(err)),
      }
    )
  }

  const openRejectModal = (row) => {
    setRejectTarget({ id: row.id, name: row.applicant_name ?? 'applicant' })
    setRejectionReason('')
  }

  const handleReject = () => {
    if (!rejectTarget) return
    decide(
      { id: rejectTarget.id, action: 'reject', rejection_reason: rejectionReason },
      {
        onSuccess: () => {
          toast.success(`Application for ${rejectTarget.name} rejected.`)
          setRejectTarget(null)
        },
        onError: (err) => toast.error(toErrorMsg(err)),
      }
    )
  }

  const openEnrollConfirm = (row) => {
    setEnrollTarget({ id: row.id, name: row.applicant_name ?? 'applicant' })
  }

  const handleEnroll = () => {
    if (!enrollTarget) return
    enroll(enrollTarget.id, {
      onSuccess: (data) => {
        const matric = data?.matric_number ?? data?.matricNumber ?? ''
        toast.success(
          matric
            ? `Student enrolled. Matric No: ${matric}`
            : `${enrollTarget.name} enrolled as student.`
        )
        setEnrollTarget(null)
      },
      onError: (err) => toast.error(toErrorMsg(err)),
    })
  }

  const columns = useMemo(
    () => [
      col.accessor((row) => row.applicant_name ?? row.applicant?.name ?? '—', {
        id: 'name',
        header: 'Applicant Name',
      }),
      col.accessor((row) => row.program?.name ?? row.program_name ?? '—', {
        id: 'program',
        header: 'Program',
      }),
      col.accessor((row) => row.session ?? row.academic_session ?? '—', {
        id: 'session',
        header: 'Session',
      }),
      col.accessor('app_status', {
        header: 'Status',
        cell: ({ getValue }) => {
          const status = getValue() ?? 'submitted'
          return (
            <Badge color={STATUS_BADGE[status] ?? 'default'}>
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </Badge>
          )
        },
      }),
      col.accessor((row) => {
        const d = row.submitted_at ?? row.created_at ?? ''
        if (!d) return '—'
        return new Date(d).toLocaleDateString('en-GB', {
          day: '2-digit', month: 'short', year: 'numeric',
        })
      }, {
        id: 'submitted_at',
        header: 'Date Submitted',
      }),
      col.display({
        id: 'actions',
        header: '',
        cell: ({ row }) => {
          const app = row.original
          const status = app.app_status ?? ''
          if (status === 'submitted' || status === 'screening') {
            return (
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="primary"
                  className="bg-emerald-600 hover:bg-emerald-700"
                  onClick={() => handleAccept(app)}
                  loading={isDeciding}
                >
                  Accept
                </Button>
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => openRejectModal(app)}
                  disabled={isDeciding}
                >
                  Reject
                </Button>
              </div>
            )
          }
          if (status === 'accepted') {
            return (
              <Button
                size="sm"
                variant="primary"
                onClick={() => openEnrollConfirm(app)}
                loading={isEnrolling}
              >
                Enroll as Student
              </Button>
            )
          }
          return <span className="text-xs text-slate-400 dark:text-slate-500">—</span>
        },
      }),
    ],
    [isDeciding, isEnrolling] // eslint-disable-line react-hooks/exhaustive-deps
  )

  return (
    <div>
      <PageHeader title="Applications" subtitle="Review and process admission applications." />

      {/* Status filter tabs */}
      <div className="flex items-center gap-1 mb-5 overflow-x-auto pb-1">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setActiveStatus(tab.value)}
            className={`shrink-0 px-4 py-1.5 rounded-full text-sm font-medium transition-colors duration-150 ${
              activeStatus === tab.value
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <Table
        columns={columns}
        data={applications}
        isLoading={isLoading}
        emptyMessage="No applications found."
      />

      {/* Reject modal */}
      <Modal
        open={!!rejectTarget}
        onClose={() => setRejectTarget(null)}
        title="Reject Application"
      >
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
          Rejecting application for <strong>{rejectTarget?.name}</strong>. Provide a reason (optional).
        </p>
        <textarea
          value={rejectionReason}
          onChange={(e) => setRejectionReason(e.target.value)}
          rows={4}
          placeholder="Rejection reason…"
          className="w-full rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:border-indigo-500 focus:ring-indigo-500/20 resize-none"
        />
        <div className="flex justify-end gap-3 mt-4">
          <Button variant="secondary" onClick={() => setRejectTarget(null)} disabled={isDeciding}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleReject} loading={isDeciding}>
            Confirm Reject
          </Button>
        </div>
      </Modal>

      {/* Enroll confirm modal */}
      <Modal
        open={!!enrollTarget}
        onClose={() => setEnrollTarget(null)}
        title="Enroll as Student"
      >
        <p className="text-sm text-slate-600 dark:text-slate-400 mb-5">
          Enroll <strong>{enrollTarget?.name}</strong> as a student? A matric number will be generated.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setEnrollTarget(null)} disabled={isEnrolling}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleEnroll} loading={isEnrolling}>
            Confirm Enroll
          </Button>
        </div>
      </Modal>
    </div>
  )
}
