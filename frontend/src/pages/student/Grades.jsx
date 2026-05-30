import { useMemo } from 'react'
import { createColumnHelper } from '@tanstack/react-table'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Badge from '../../components/ui/Badge'
import Card, { CardBody } from '../../components/ui/Card'
import { useMyStudentRecord } from '../../features/students/queries'
import { useTranscript } from '../../features/grades/queries'

const col = createColumnHelper()

function gradeColor(passed) {
  if (passed === true) return 'success'
  if (passed === false) return 'danger'
  return 'default'
}

export default function Grades() {
  useTitle('My Grades')

  const { data: studentRecord, isLoading: loadingStudent } = useMyStudentRecord()
  const studentId = studentRecord?.id ?? studentRecord?.student_id ?? null

  const { data: transcript, isLoading: loadingTranscript } = useTranscript(studentId)

  const isLoading = loadingStudent || loadingTranscript

  const records = transcript?.records ?? transcript?.grades ?? transcript?.courses ?? []
  const cgpa = transcript?.cgpa ?? transcript?.CGPA ?? '—'
  const totalPassed = transcript?.total_credits_passed ?? transcript?.credits_passed ?? '—'

  const columns = useMemo(
    () => [
      col.accessor((row) => row.course?.code ?? row.course_code ?? '—', {
        id: 'code',
        header: 'Course Code',
      }),
      col.accessor((row) => row.course?.title ?? row.course_title ?? '—', {
        id: 'title',
        header: 'Title',
      }),
      col.accessor((row) => row.course?.credit_hours ?? row.credit_hours ?? '—', {
        id: 'credits',
        header: 'Credits',
      }),
      col.accessor((row) => row.ca_score ?? row.ca ?? '—', {
        id: 'ca',
        header: 'CA',
      }),
      col.accessor((row) => row.exam_score ?? row.exam ?? '—', {
        id: 'exam',
        header: 'Exam',
      }),
      col.accessor((row) => row.total_score ?? row.total ?? '—', {
        id: 'total',
        header: 'Total',
      }),
      col.accessor((row) => row.grade ?? '—', {
        id: 'grade',
        header: 'Grade',
      }),
      col.display({
        id: 'status',
        header: 'Status',
        cell: ({ row }) => {
          const r = row.original
          const passed = r.passed ?? (r.grade && !['F', 'E'].includes(r.grade.toUpperCase()))
          return (
            <Badge color={gradeColor(passed)}>
              {passed === true ? 'Pass' : passed === false ? 'Fail' : '—'}
            </Badge>
          )
        },
      }),
    ],
    []
  )

  return (
    <div>
      <PageHeader
        title="My Transcript"
        subtitle="Your academic performance record."
      />

      <div className="grid grid-cols-2 gap-4 mb-6">
        <Card>
          <CardBody className="py-5">
            <p className="text-xs text-slate-500 dark:text-slate-400">CGPA</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">
              {isLoading ? '...' : cgpa}
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-5">
            <p className="text-xs text-slate-500 dark:text-slate-400">Total Credits Passed</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">
              {isLoading ? '...' : totalPassed}
            </p>
          </CardBody>
        </Card>
      </div>

      <Table
        columns={columns}
        data={records}
        isLoading={isLoading}
        emptyMessage="No grade records available."
      />
    </div>
  )
}
