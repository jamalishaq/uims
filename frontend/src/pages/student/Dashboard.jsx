import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import Card, { CardBody } from '../../components/ui/Card'
import PageHeader from '../../components/PageHeader'
import { useMyEnrollments } from '../../features/enrollment/queries'
import { useMyStudentRecord } from '../../features/students/queries'
import { useTranscript } from '../../features/grades/queries'

export default function StudentDashboard() {
  useTitle('Dashboard')
  const { username } = useAuth()

  const { data: enrollments = [], isLoading: loadingEnrollments } = useMyEnrollments()
  const { data: studentRecord, isLoading: loadingStudent } = useMyStudentRecord()

  const studentId = studentRecord?.id ?? studentRecord?.student_id ?? null
  const { data: transcript, isLoading: loadingTranscript } = useTranscript(studentId)

  const enrolledCount = enrollments.length
  const totalCredits = enrollments.reduce((sum, e) => {
    const ch = e.section?.course?.credit_hours ?? e.credit_hours ?? 0
    return sum + Number(ch)
  }, 0)

  const cgpa = transcript?.cgpa ?? transcript?.CGPA ?? null
  const totalCreditsPassed = transcript?.total_credits_passed ?? transcript?.credits_passed ?? null

  const loading = loadingEnrollments || loadingStudent || loadingTranscript

  const stats = [
    { label: 'Enrolled Courses', value: loadingEnrollments ? '...' : enrolledCount },
    { label: 'Credit Hours', value: loadingEnrollments ? '...' : totalCredits },
    { label: 'CGPA', value: loading ? '...' : cgpa != null ? Number(cgpa).toFixed(2) : '—' },
    { label: 'Credits Passed', value: loading ? '...' : totalCreditsPassed ?? '—' },
  ]

  return (
    <div>
      <PageHeader
        title={`Welcome, ${username ?? 'Student'}`}
        subtitle="Here's your academic overview for this semester."
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {stats.map(({ label, value }) => (
          <Card key={label}>
            <CardBody className="py-5">
              <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
              <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">{value}</p>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  )
}
