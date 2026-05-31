import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody } from '../../components/ui/Card'
import { useAcademicStats } from '../../features/academic/queries'

const STAT_KEYS = [
  { key: 'faculties',    label: 'Faculties' },
  { key: 'departments',  label: 'Departments' },
  { key: 'programs',     label: 'Programs' },
  { key: 'total_users',  label: 'Total Users' },
]

export default function SuperAdminDashboard() {
  useTitle('Dashboard')
  const { username } = useAuth()
  const { data, isLoading } = useAcademicStats()

  return (
    <div>
      <PageHeader title={`Welcome, ${username ?? 'Admin'}`} subtitle="University overview" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STAT_KEYS.map(({ key, label }) => (
          <Card key={key}>
            <CardBody className="py-5">
              <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
              <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">
                {isLoading ? (
                  <span className="inline-block h-7 w-12 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                ) : (
                  data?.[key] ?? '—'
                )}
              </p>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  )
}
