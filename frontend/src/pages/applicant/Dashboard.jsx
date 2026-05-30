import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody } from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'

export default function ApplicantDashboard() {
  useTitle('Dashboard')
  const { username } = useAuth()

  return (
    <div>
      <PageHeader
        title={`Welcome, ${username ?? 'Applicant'}`}
        subtitle="Track your admission application status below."
      />
      <Card className="max-w-md">
        <CardBody>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
            Application Status
          </p>
          <Badge color="warning">Pending Review</Badge>
        </CardBody>
      </Card>
    </div>
  )
}
