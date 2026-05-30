import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import Card, { CardBody } from '../../components/ui/Card'
import PageHeader from '../../components/PageHeader'

const stats = [
  { label: 'Enrolled Courses',  value: '—' },
  { label: 'Credit Hours',      value: '—' },
  { label: 'Current GPA',       value: '—' },
  { label: 'CGPA',              value: '—' },
]

export default function StudentDashboard() {
  useTitle('Dashboard')
  const { username } = useAuth()

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
