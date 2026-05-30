import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardHeader, CardBody } from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Select from '../../components/ui/Select'
import { useStudent, useUpdateStudentStatus } from '../../features/students/queries'

const STUDENT_STATUSES = ['active', 'inactive', 'graduated', 'withdrawn', 'suspended']

const STATUS_BADGE = {
  active:    'success',
  inactive:  'warning',
  graduated: 'indigo',
  withdrawn: 'danger',
  suspended: 'danger',
}

function InfoRow({ label, value }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-0.5 sm:gap-4 py-2.5 border-b border-slate-100 dark:border-slate-800 last:border-0">
      <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide sm:w-40 shrink-0">
        {label}
      </span>
      <span className="text-sm text-slate-900 dark:text-slate-100">{value ?? '—'}</span>
    </div>
  )
}

function toErrorMsg(err) {
  return (
    err?.response?.data?.detail ||
    err?.response?.data?.message ||
    err?.message ||
    'Something went wrong'
  )
}

export default function StudentDetail() {
  const { studentId } = useParams()
  const navigate = useNavigate()

  const { data: student, isLoading, isError } = useStudent(studentId)
  useTitle(student ? `Student — ${student.matric_number ?? student.username ?? studentId}` : 'Student Detail')

  const [selectedStatus, setSelectedStatus] = useState('')
  const { mutate: updateStatus, isPending: isSaving } = useUpdateStudentStatus()

  const handleSaveStatus = () => {
    if (!selectedStatus) return
    updateStatus(
      { id: studentId, status: selectedStatus },
      {
        onSuccess: () => toast.success(`Status updated to "${selectedStatus}".`),
        onError: (err) => toast.error(toErrorMsg(err)),
      }
    )
  }

  if (isLoading) {
    return (
      <div>
        <PageHeader title="Student Detail" />
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-16 rounded-xl bg-slate-100 dark:bg-slate-800 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (isError || !student) {
    return (
      <div>
        <PageHeader title="Student Detail" />
        <Card>
          <CardBody>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Student record not found or failed to load.
            </p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={() => navigate(-1)}>
              Go Back
            </Button>
          </CardBody>
        </Card>
      </div>
    )
  }

  const currentStatus = student.status ?? ''
  const name =
    student.full_name ??
    student.name ??
    [student.first_name, student.last_name].filter(Boolean).join(' ') ||
    student.username ??
    '—'

  const enrollments = student.enrollments ?? student.current_enrollments ?? []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Student Detail"
        action={
          <Button variant="secondary" size="sm" onClick={() => navigate(-1)}>
            Back
          </Button>
        }
      />

      {/* Profile card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            {/* Avatar initials */}
            <div className="h-12 w-12 rounded-full bg-indigo-100 dark:bg-indigo-900 flex items-center justify-center shrink-0">
              <span className="text-lg font-semibold text-indigo-700 dark:text-indigo-300">
                {name.charAt(0).toUpperCase()}
              </span>
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">{name}</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                {student.matric_number ?? student.matricNumber ?? 'No matric number'}
              </p>
            </div>
            <div className="ml-auto">
              <Badge color={STATUS_BADGE[currentStatus] ?? 'default'}>
                {currentStatus ? currentStatus.charAt(0).toUpperCase() + currentStatus.slice(1) : '—'}
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardBody>
          <InfoRow label="Matric Number" value={student.matric_number ?? student.matricNumber} />
          <InfoRow label="Username" value={student.username ?? student.user?.username} />
          <InfoRow label="Email" value={student.email ?? student.user?.email} />
          <InfoRow label="Program" value={student.program?.name ?? student.program_name} />
          <InfoRow label="Level" value={student.level ? `${student.level} Level` : undefined} />
          <InfoRow
            label="CGPA"
            value={
              student.cgpa != null
                ? Number(student.cgpa).toFixed(2)
                : student.gpa != null
                ? Number(student.gpa).toFixed(2)
                : undefined
            }
          />
          <InfoRow
            label="Credits Passed"
            value={student.credits_passed ?? student.total_credits_passed}
          />
        </CardBody>
      </Card>

      {/* Change status */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Change Status</h3>
        </CardHeader>
        <CardBody>
          <div className="flex items-end gap-3">
            <Select
              label="New Status"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="max-w-xs"
            >
              <option value="">— Select status —</option>
              {STUDENT_STATUSES.map((s) => (
                <option key={s} value={s} disabled={s === currentStatus}>
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                  {s === currentStatus ? ' (current)' : ''}
                </option>
              ))}
            </Select>
            <Button
              variant="primary"
              disabled={!selectedStatus || selectedStatus === currentStatus}
              loading={isSaving}
              onClick={handleSaveStatus}
            >
              Save
            </Button>
          </div>
        </CardBody>
      </Card>

      {/* Current enrollments */}
      {enrollments.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Current Enrollments
            </h3>
          </CardHeader>
          <CardBody className="p-0">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800/60">
                <tr>
                  {['Course Code', 'Course Title', 'Credits', 'Grade', 'Status'].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {enrollments.map((enr, idx) => (
                  <tr
                    key={enr.id ?? idx}
                    className="border-t border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
                  >
                    <td className="px-4 py-3 text-slate-700 dark:text-slate-300 font-mono text-xs">
                      {enr.course_code ?? enr.course?.code ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                      {enr.course_title ?? enr.course?.title ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                      {enr.credit_hours ?? enr.course?.credit_hours ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-700 dark:text-slate-300">
                      {enr.grade ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Badge color={enr.status === 'active' ? 'success' : 'default'}>
                        {enr.status ?? 'active'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
