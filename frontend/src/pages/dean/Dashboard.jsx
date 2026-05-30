import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody } from '../../components/ui/Card'

const stats = [
  { label: 'Departments',         value: '—' },
  { label: 'Total Students',      value: '—' },
  { label: 'Pending Ratification',value: '—' },
]

export default function DeanDashboard() {
  useTitle('Dashboard')
  const { username } = useAuth()

  return (
    <div>
      <PageHeader title={`Welcome, ${username ?? 'Dean'}`} subtitle="Faculty overview" />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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
