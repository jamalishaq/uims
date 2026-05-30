import { useMemo, useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table, { createColumnHelper } from '../../components/ui/Table'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import Badge from '../../components/ui/Badge'
import { useSections } from '../../features/courses/queries'
import { useSectionEnrollments } from '../../features/courses/queries'
import { useAttendanceSummary, useMarkAttendance } from '../../features/attendance/queries'

const col = createColumnHelper()
const THRESHOLD = 75

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

export default function Attendance() {
  useTitle('Attendance')
  const { sub: user_id } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const paramSection = searchParams.get('section')

  const [sectionId, setSectionId] = useState(paramSection ?? '')
  const [markOpen, setMarkOpen] = useState(false)
  const [date, setDate] = useState(todayStr())
  const [statuses, setStatuses] = useState({})

  const { data: sections = [] } = useSections(user_id ? { lecturer_id: user_id } : undefined)
  const { data: summary = [], isLoading: summaryLoading } = useAttendanceSummary(sectionId || null)
  const { data: enrollments = [], isLoading: enrollLoading } = useSectionEnrollments(sectionId || null)
  const { mutate: markAttendance, isPending } = useMarkAttendance()

  // Sync URL param → local state
  useEffect(() => {
    if (paramSection && paramSection !== sectionId) setSectionId(paramSection)
  }, [paramSection]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleSectionChange(e) {
    const val = e.target.value
    setSectionId(val)
    if (val) setSearchParams({ section: val })
    else setSearchParams({})
  }

  function openMarkModal() {
    // Initialize all students as Present
    const initial = {}
    enrollments.forEach((en) => {
      initial[en.id] = 'present'
    })
    setStatuses(initial)
    setDate(todayStr())
    setMarkOpen(true)
  }

  function handleStatusChange(enrollmentId, value) {
    setStatuses((prev) => ({ ...prev, [enrollmentId]: value }))
  }

  function handleSubmit() {
    const records = Object.entries(statuses).map(([enrollmentId, status]) => ({
      enrollment_id: Number(enrollmentId),
      status,
    }))
    markAttendance(
      { sectionId, date, records },
      {
        onSuccess: () => {
          toast.success('Attendance marked successfully.')
          setMarkOpen(false)
        },
        onError: (err) => {
          toast.error(err?.response?.data?.detail || err?.message || 'Failed to mark attendance.')
        },
      },
    )
  }

  const summaryColumns = useMemo(
    () => [
      col.accessor('matric_number', { header: 'Matric No.' }),
      col.accessor('student_name', { header: 'Student Name' }),
      col.accessor('total_classes', { header: 'Total' }),
      col.accessor('attended', { header: 'Attended' }),
      col.accessor('percentage', {
        header: '%',
        cell: (info) => {
          const pct = info.getValue()
          const num = typeof pct === 'number' ? pct : parseFloat(pct)
          const color = num < THRESHOLD ? 'danger' : 'success'
          return (
            <span className="flex items-center gap-2">
              <span>{isNaN(num) ? '—' : `${num.toFixed(1)}%`}</span>
              {num < THRESHOLD && <Badge color={color}>Below {THRESHOLD}%</Badge>}
            </span>
          )
        },
      }),
    ],
    [],
  )

  return (
    <div>
      <PageHeader
        title="Attendance"
        subtitle="View summaries and mark attendance for your sections."
        action={
          sectionId && (
            <Button onClick={openMarkModal} disabled={enrollLoading}>
              Mark Today's Attendance
            </Button>
          )
        }
      />

      {/* Section selector */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
          Select Section
        </label>
        <select
          value={sectionId}
          onChange={handleSectionChange}
          className="w-full max-w-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
        >
          <option value="">— Choose a section —</option>
          {sections.map((s) => (
            <option key={s.id} value={s.id}>
              {s.course_code} — {s.course_title} ({s.semester})
            </option>
          ))}
        </select>
      </div>

      {sectionId ? (
        <Table
          columns={summaryColumns}
          data={summary}
          isLoading={summaryLoading}
          emptyMessage="No attendance records yet for this section."
        />
      ) : (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Select a section above to view attendance records.
        </p>
      )}

      {/* Mark Attendance Modal */}
      <Modal
        open={markOpen}
        onClose={() => setMarkOpen(false)}
        title="Mark Attendance"
        className="max-w-2xl"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
              Date
            </label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          </div>

          <div className="max-h-96 overflow-y-auto divide-y divide-slate-200 dark:divide-slate-700 border border-slate-200 dark:border-slate-700 rounded-lg">
            {enrollments.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400 px-4 py-3">
                No students enrolled in this section.
              </p>
            ) : (
              enrollments.map((en) => (
                <div
                  key={en.id}
                  className="flex items-center justify-between px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/40"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                      {en.student_name}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{en.matric_number}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    {['present', 'absent', 'excused'].map((status) => (
                      <label
                        key={status}
                        className="flex items-center gap-1.5 cursor-pointer text-sm capitalize text-slate-700 dark:text-slate-300"
                      >
                        <input
                          type="radio"
                          name={`status-${en.id}`}
                          value={status}
                          checked={statuses[en.id] === status}
                          onChange={() => handleStatusChange(en.id, status)}
                          className="accent-indigo-600"
                        />
                        {status}
                      </label>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setMarkOpen(false)}>
              Cancel
            </Button>
            <Button loading={isPending} onClick={handleSubmit}>
              Submit Attendance
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
