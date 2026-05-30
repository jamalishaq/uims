import { useState, useMemo } from 'react'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardHeader, CardBody } from '../../components/ui/Card'
import Table, { createColumnHelper } from '../../components/ui/Table'
import Badge from '../../components/ui/Badge'
import Select from '../../components/ui/Select'
import { useEnrollmentStats, usePassFailRates } from '../../features/reports/queries'
import { useSessions } from '../../features/academic/queries'

// ── column helpers ────────────────────────────────────────────────────────────
const enrollCol = createColumnHelper()
const passFailCol = createColumnHelper()

const enrollmentColumns = [
  enrollCol.accessor('program_name', { header: 'Program' }),
  enrollCol.accessor('level',        { header: 'Level' }),
  enrollCol.accessor('student_count',{ header: 'Students', enableSorting: true }),
]

function passRateBadge(rate) {
  if (rate >= 70) return <Badge color="success">{rate.toFixed(1)}%</Badge>
  if (rate >= 50) return <Badge color="warning">{rate.toFixed(1)}%</Badge>
  return <Badge color="danger">{rate.toFixed(1)}%</Badge>
}

const passFailColumns = [
  passFailCol.accessor('course_code',  { header: 'Code' }),
  passFailCol.accessor('course_title', { header: 'Course Title' }),
  passFailCol.accessor('total',        { header: 'Total', enableSorting: true }),
  passFailCol.accessor('passed',       { header: 'Passed', enableSorting: true }),
  passFailCol.accessor('failed',       { header: 'Failed', enableSorting: true }),
  passFailCol.accessor('pass_rate', {
    header: 'Pass Rate',
    enableSorting: true,
    cell: (info) => passRateBadge(info.getValue() ?? 0),
  }),
]

// ── component ─────────────────────────────────────────────────────────────────
export default function HODReports() {
  useTitle('Reports')

  const { data: sessions = [], isLoading: sessionsLoading } = useSessions()

  // flatten sessions → semesters
  const semesters = useMemo(() => {
    const list = []
    sessions.forEach((sess) => {
      ;(sess.semesters ?? []).forEach((sem) => {
        list.push({ id: sem.id, label: `${sess.name} — ${sem.name}` })
      })
    })
    return list
  }, [sessions])

  const [semesterId, setSemesterId] = useState('')

  const params = semesterId ? { semester_id: semesterId } : undefined

  const { data: enrollmentStats = [], isLoading: enrollLoading } = useEnrollmentStats(params)
  const { data: passFailRates  = [], isLoading: passFailLoading } = usePassFailRates(params)

  const enrollTotal = useMemo(
    () => enrollmentStats.reduce((sum, r) => sum + (r.student_count ?? 0), 0),
    [enrollmentStats]
  )

  const enrollDataWithTotal = useMemo(() => {
    if (enrollmentStats.length === 0) return []
    return [
      ...enrollmentStats,
      { program_name: 'Total', level: '', student_count: enrollTotal, _isTotal: true },
    ]
  }, [enrollmentStats, enrollTotal])

  return (
    <div className="space-y-6">
      <PageHeader title="Reports" subtitle="Enrollment and pass/fail data by semester" />

      {/* Semester selector */}
      <Card>
        <CardBody>
          <div className="max-w-xs">
            <Select
              label="Semester"
              value={semesterId}
              onChange={(e) => setSemesterId(e.target.value)}
              disabled={sessionsLoading}
            >
              <option value="">All semesters</option>
              {semesters.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </Select>
          </div>
        </CardBody>
      </Card>

      {/* Enrollment stats */}
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Enrollment Statistics
          </h2>
        </CardHeader>
        <div className="overflow-x-auto">
          <Table
            columns={enrollmentColumns}
            data={enrollDataWithTotal}
            isLoading={enrollLoading}
            emptyMessage="No enrollment data"
          />
        </div>
      </Card>

      {/* Pass / fail rates */}
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Pass / Fail Rates
          </h2>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            <span className="inline-flex gap-2 items-center">
              <Badge color="success">green</Badge> ≥ 70%
              <Badge color="warning">amber</Badge> 50–70%
              <Badge color="danger">red</Badge> &lt; 50%
            </span>
          </p>
        </CardHeader>
        <div className="overflow-x-auto">
          <Table
            columns={passFailColumns}
            data={passFailRates}
            isLoading={passFailLoading}
            emptyMessage="No pass/fail data"
          />
        </div>
      </Card>
    </div>
  )
}
