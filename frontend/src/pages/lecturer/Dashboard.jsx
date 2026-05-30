import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody } from '../../components/ui/Card'
import { useSections } from '../../features/courses/queries'
import { useSectionGrades } from '../../features/grades/queries'

function StatCard({ label, value, loading }) {
  return (
    <Card>
      <CardBody className="py-5">
        <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
        {loading ? (
          <div className="mt-1 h-8 w-16 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
        ) : (
          <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">{value}</p>
        )}
      </CardBody>
    </Card>
  )
}

export default function LecturerDashboard() {
  useTitle('Dashboard')
  const { username, user_id } = useAuth()

  const { data: sections = [], isLoading: sectionsLoading } = useSections(
    user_id ? { lecturer_id: user_id } : undefined,
  )

  // Total students across all sections
  const totalStudents = sections.reduce((sum, s) => sum + (s.enrolled_count ?? 0), 0)

  // Count sections that still have enrollments without a grade (pending grades)
  // We do a lightweight approach: sections where enrolled_count > 0 and graded_count < enrolled_count
  const pendingGrades = sections.reduce((sum, s) => {
    const graded = s.graded_count ?? 0
    const enrolled = s.enrolled_count ?? 0
    return sum + Math.max(enrolled - graded, 0)
  }, 0)

  const stats = [
    {
      label: 'Course Sections',
      value: sectionsLoading ? null : sections.length,
      loading: sectionsLoading,
    },
    {
      label: 'Total Students',
      value: sectionsLoading ? null : totalStudents,
      loading: sectionsLoading,
    },
    {
      label: 'Pending Grades',
      value: sectionsLoading ? null : pendingGrades || '—',
      loading: sectionsLoading,
    },
  ]

  return (
    <div>
      <PageHeader
        title={`Welcome, ${username ?? 'Lecturer'}`}
        subtitle="Here's your teaching overview for this semester."
      />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {stats.map(({ label, value, loading }) => (
          <StatCard key={label} label={label} value={value} loading={loading} />
        ))}
      </div>
    </div>
  )
}
