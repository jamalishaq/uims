import { Link } from 'react-router-dom'
import {
  Building2,
  BookOpen,
  CalendarDays,
  KeyRound,
  Wallet,
} from 'lucide-react'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import PageHeader, { StatTile } from '../../components/PageHeader'
import { Note } from '../../components/ui/Feedback'
import { useCredentials } from '../../features/auth/queries'
import useTitle from '../../hooks/useTitle'

const AREAS = [
  {
    to: '../structure',
    icon: Building2,
    title: 'Structure',
    body: 'Create faculties, and read where a programme sits for a session.',
  },
  {
    to: '../sessions',
    icon: CalendarDays,
    title: 'Sessions',
    body: 'Describe a session, then open it — which bills the cohort.',
  },
  {
    to: '../courses',
    icon: BookOpen,
    title: 'Courses',
    body: 'The catalogue: credit units, prerequisites, retirement.',
  },
  {
    to: '../bursary',
    icon: Wallet,
    title: 'Bursary',
    body: 'Ledgers, payments, session fees and the reconciliation sweep.',
  },
  {
    to: '../credentials',
    icon: KeyRound,
    title: 'Credentials',
    body: 'Who can sign in, at which level, and for which unit.',
  },
]

/**
 * The university-wide home.
 *
 * The one real figure available is the credential count — `GET /auth/credentials` is the only
 * route in the system that enumerates anything university-wide. Everything else is keyed by an
 * id, so the rest of this page is navigation rather than invented statistics.
 */
export default function UniversityOverview() {
  useTitle('Overview')
  const credentials = useCredentials()

  const byRole = (credentials.data ?? []).reduce((counts, credential) => {
    counts[credential.role] = (counts[credential.role] ?? 0) + 1
    return counts
  }, {})

  return (
    <>
      <PageHeader
        title="University"
        description="Everything in the system is reachable from here."
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Logins"
          value={credentials.data?.length ?? '—'}
          caption="Every credential held"
        />
        <StatTile label="Departments" value={byRole.department ?? '—'} caption="With a login" />
        <StatTile label="Lecturers" value={byRole.lecturer ?? '—'} caption="With a login" />
        <StatTile label="Students" value={byRole.student ?? '—'} caption="With a login" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {AREAS.map(({ to, icon: Icon, title, body }) => (
          <Link key={to} to={to} className="group">
            <Card className="h-full transition-shadow hover:shadow-raised">
              <CardBody>
                <span className="inline-grid h-9 w-9 place-items-center rounded-lg bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-300">
                  <Icon size={18} aria-hidden="true" />
                </span>
                <h2 className="mt-3 text-sm font-semibold text-ink-900 group-hover:text-brand-700 dark:text-ink-100 dark:group-hover:text-brand-400">
                  {title}
                </h2>
                <p className="mt-1 text-sm text-ink-500 dark:text-ink-400">{body}</p>
              </CardBody>
            </Card>
          </Link>
        ))}
      </div>

      <Card className="mt-6">
        <CardHeader title="Counts are of logins, not of things" />
        <CardBody>
          <Note tone="info">
            The tiles above count <strong>credentials</strong>, because that is the only
            university-wide list the API offers. A department with no login does not appear, and
            a student who has not been given one does not either. They are a rough shape of the
            university, not its register.
          </Note>
        </CardBody>
      </Card>
    </>
  )
}
