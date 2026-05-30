import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Badge from '../../components/ui/Badge'
import Card, { CardBody } from '../../components/ui/Card'
import EmptyState from '../../components/EmptyState'
import { useMyAttendance } from '../../features/attendance/queries'

function attendanceBadge(pct) {
  if (pct == null) return { color: 'default', label: '—' }
  if (pct >= 75) return { color: 'success', label: `${pct.toFixed(1)}%` }
  if (pct >= 50) return { color: 'warning', label: `${pct.toFixed(1)}% — Low` }
  return { color: 'danger', label: `${pct.toFixed(1)}% — Critical` }
}

function AttendanceCard({ record }) {
  const total = record.total_classes ?? record.total ?? 0
  const attended = record.attended ?? record.present ?? 0
  const pct = total > 0 ? (attended / total) * 100 : null
  const badge = attendanceBadge(pct)

  const courseName =
    record.course?.title ??
    record.course_title ??
    record.section?.course?.title ??
    record.section_name ??
    '—'
  const courseCode =
    record.course?.code ??
    record.course_code ??
    record.section?.course?.code ??
    ''

  return (
    <Card>
      <CardBody>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">
              {courseCode}
            </p>
            <p className="mt-0.5 text-sm font-semibold text-slate-900 dark:text-slate-100">{courseName}</p>
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
              Attended <span className="font-medium text-slate-700 dark:text-slate-300">{attended}</span>{' '}
              of <span className="font-medium text-slate-700 dark:text-slate-300">{total}</span> classes
            </p>
          </div>
          <Badge color={badge.color} className="shrink-0 mt-1">
            {badge.label}
          </Badge>
        </div>

        {/* Progress bar */}
        <div className="mt-3 h-1.5 w-full rounded-full bg-slate-100 dark:bg-slate-800">
          <div
            className={`h-1.5 rounded-full transition-all ${
              pct == null
                ? 'w-0'
                : pct >= 75
                ? 'bg-emerald-500'
                : pct >= 50
                ? 'bg-amber-500'
                : 'bg-red-500'
            }`}
            style={{ width: pct != null ? `${Math.min(pct, 100)}%` : '0%' }}
          />
        </div>

        {pct != null && pct < 75 && (
          <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
            Warning: Attendance below 75% may affect your grades.
          </p>
        )}
      </CardBody>
    </Card>
  )
}

export default function Attendance() {
  useTitle('My Attendance')

  const { data: records = [], isLoading } = useMyAttendance()

  return (
    <div>
      <PageHeader
        title="My Attendance"
        subtitle="Track your attendance across all enrolled courses."
      />

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardBody>
                <div className="space-y-2">
                  <div className="h-3 w-16 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                  <div className="h-4 w-32 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                  <div className="h-3 w-24 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                </div>
              </CardBody>
            </Card>
          ))}
        </div>
      ) : records.length === 0 ? (
        <EmptyState title="No attendance records found." />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {records.map((record, idx) => (
            <AttendanceCard key={record.id ?? record.section_id ?? idx} record={record} />
          ))}
        </div>
      )}
    </div>
  )
}
