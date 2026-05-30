import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody } from '../../components/ui/Card'

export default function AlumniDashboard() {
  useTitle('Dashboard')
  const { username } = useAuth()

  return (
    <div>
      <PageHeader
        title={`Welcome, ${username ?? 'Alumni'}`}
        subtitle="Access your transcript and alumni services below."
      />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-lg">
        <Card>
          <CardBody className="py-5">
            <p className="text-xs text-slate-500 dark:text-slate-400">Graduation Year</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">—</p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-5">
            <p className="text-xs text-slate-500 dark:text-slate-400">Final CGPA</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">—</p>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
