import { useState, useMemo } from 'react'
import useTitle from '../../hooks/useTitle'
import useAuth from '../../hooks/useAuth'
import PageHeader from '../../components/PageHeader'
import Card, { CardHeader, CardBody } from '../../components/ui/Card'
import Table, { createColumnHelper } from '../../components/ui/Table'
import Badge from '../../components/ui/Badge'
import Select from '../../components/ui/Select'
import { useSections } from '../../features/courses/queries'
import { useAttendanceSummary } from '../../features/attendance/queries'

const col = createColumnHelper()

const columns = [
  col.accessor('matric_number', { header: 'Matric No.' }),
  col.accessor('student_name',  { header: 'Student' }),
  col.accessor('total_classes', {
    header: 'Total',
    enableSorting: true,
    cell: (info) => info.getValue() ?? '—',
  }),
  col.accessor('attended', {
    header: 'Attended',
    enableSorting: true,
    cell: (info) => info.getValue() ?? '—',
  }),
  col.accessor('attendance_percentage', {
    header: '%',
    enableSorting: true,
    cell: (info) => {
      const val = info.getValue()
      if (val == null) return '—'
      return `${Number(val).toFixed(1)}%`
    },
  }),
  col.accessor('below_threshold', {
    header: 'Status',
    cell: (info) =>
      info.getValue() ? (
        <Badge color="danger">Below threshold</Badge>
      ) : (
        <Badge color="success">OK</Badge>
      ),
  }),
]

export default function HODAttendance() {
  useTitle('Attendance Oversight')
  const { department_id } = useAuth()

  // Fetch sections filtered to HOD's department
  const { data: sections = [], isLoading: sectionsLoading } = useSections(
    department_id ? { department_id } : undefined
  )

  const [sectionId, setSectionId] = useState('')

  const { data: summary = [], isLoading: summaryLoading } = useAttendanceSummary(
    sectionId || undefined
  )

  // Build section label: course_code + section label if available
  const sectionOptions = useMemo(
    () =>
      sections.map((s) => ({
        id: s.id,
        label: [s.course_code, s.course_title, s.label].filter(Boolean).join(' — '),
      })),
    [sections]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Attendance Oversight"
        subtitle="Review attendance summaries by section"
      />

      {/* Section selector */}
      <Card>
        <CardBody>
          <div className="max-w-sm">
            <Select
              label="Section"
              value={sectionId}
              onChange={(e) => setSectionId(e.target.value)}
              disabled={sectionsLoading}
            >
              <option value="">Select a section…</option>
              {sectionOptions.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </Select>
          </div>
        </CardBody>
      </Card>

      {/* Attendance summary table */}
      {sectionId && (
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Attendance Summary
            </h2>
            {!summaryLoading && summary.length > 0 && (
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                {summary.filter((r) => r.below_threshold).length} student(s) below threshold
              </p>
            )}
          </CardHeader>
          <div className="overflow-x-auto">
            <Table
              columns={columns}
              data={summary}
              isLoading={summaryLoading}
              emptyMessage="No attendance records for this section"
            />
          </div>
        </Card>
      )}

      {!sectionId && !sectionsLoading && (
        <Card>
          <CardBody>
            <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-6">
              Select a section above to view attendance data.
            </p>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
