import { useMemo } from 'react'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody } from '../../components/ui/Card'
import Table, { createColumnHelper } from '../../components/ui/Table'
import Badge from '../../components/ui/Badge'
import { useMyStudentRecord } from '../../features/students/queries'
import { useTranscript } from '../../features/transcript/queries'

const columnHelper = createColumnHelper()

const columns = [
  columnHelper.accessor('course_code', {
    header: 'Code',
    cell: (info) => (
      <span className="font-mono text-xs text-slate-700 dark:text-slate-300">
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor('course_title', {
    header: 'Course Title',
    cell: (info) => (
      <span className="font-medium text-slate-800 dark:text-slate-200">
        {info.getValue()}
      </span>
    ),
  }),
  columnHelper.accessor('credit_units', {
    header: 'Credits',
    cell: (info) => info.getValue() ?? '—',
  }),
  columnHelper.accessor('ca_score', {
    header: 'CA',
    cell: (info) => (info.getValue() != null ? info.getValue() : '—'),
  }),
  columnHelper.accessor('exam_score', {
    header: 'Exam',
    cell: (info) => (info.getValue() != null ? info.getValue() : '—'),
  }),
  columnHelper.accessor('total_score', {
    header: 'Total',
    cell: (info) => (info.getValue() != null ? info.getValue() : '—'),
  }),
  columnHelper.accessor('grade', {
    header: 'Grade',
    cell: (info) => (
      <span className="font-semibold text-slate-900 dark:text-slate-100">
        {info.getValue() ?? '—'}
      </span>
    ),
  }),
  columnHelper.accessor('passed', {
    header: 'Status',
    enableSorting: false,
    cell: (info) => {
      const passed = info.getValue()
      if (passed == null) return <span className="text-slate-400">—</span>
      return (
        <Badge color={passed ? 'success' : 'danger'}>
          {passed ? 'Pass' : 'Fail'}
        </Badge>
      )
    },
  }),
]

export default function AlumniTranscript() {
  useTitle('Transcript')

  const { data: studentRecord, isLoading: studentLoading, isError: studentError } =
    useMyStudentRecord()

  const studentId = studentRecord?.id ?? studentRecord?.student_id ?? null

  const {
    data: transcript,
    isLoading: transcriptLoading,
    isError: transcriptError,
  } = useTranscript(studentId)

  const grades = useMemo(() => transcript?.grades ?? transcript ?? [], [transcript])

  const cgpa = transcript?.cgpa ?? null
  const totalCredits = transcript?.total_credits_passed ?? transcript?.total_credits ?? null

  const isLoading = studentLoading || transcriptLoading
  const isError = studentError || transcriptError

  return (
    <div>
      <PageHeader
        title="My Transcript"
        subtitle="Your full academic record and performance summary."
      />

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6 max-w-lg">
        <Card>
          <CardBody className="py-5">
            <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
              CGPA
            </p>
            {isLoading ? (
              <div className="mt-1 h-8 w-20 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
            ) : (
              <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">
                {cgpa != null ? Number(cgpa).toFixed(2) : '—'}
              </p>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardBody className="py-5">
            <p className="text-xs text-slate-500 dark:text-slate-400 uppercase tracking-wide">
              Credits Passed
            </p>
            {isLoading ? (
              <div className="mt-1 h-8 w-16 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
            ) : (
              <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">
                {totalCredits != null ? totalCredits : '—'}
              </p>
            )}
          </CardBody>
        </Card>
      </div>

      {/* Error state */}
      {isError && !isLoading && (
        <Card className="mb-6">
          <CardBody>
            <p className="text-sm text-red-600 dark:text-red-400">
              Failed to load transcript. Please try again later.
            </p>
          </CardBody>
        </Card>
      )}

      {/* Grades table */}
      <Card>
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Course Grades
          </h2>
        </div>
        <Table
          columns={columns}
          data={grades}
          isLoading={isLoading}
          emptyMessage="No grades recorded yet."
        />
      </Card>
    </div>
  )
}
