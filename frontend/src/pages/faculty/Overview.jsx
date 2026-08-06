import { Link } from 'react-router-dom'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import PageHeader from '../../components/PageHeader'
import { Note } from '../../components/ui/Feedback'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * The faculty office's home.
 *
 * **It shows no counts, and that is a property of the API rather than a gap.** Nothing
 * enumerates the departments in a faculty: Faculty & Department has `POST /departments` and
 * reads keyed by a department id you already hold, but no `GET /faculties/{id}/departments`.
 * A tile reading "4 departments" would have to be assembled from a list this app does not have
 * and would end up being a second, quietly diverging copy of the university's structure.
 *
 * So this page says what the office can *do* rather than inventing a dashboard. The two acts a
 * faculty officer has are both real routes.
 */
export default function FacultyOverview() {
  useTitle('Overview')
  const { scopeId } = useAuth()

  return (
    <>
      <PageHeader
        title="Faculty office"
        description={
          <>
            Acting for <span className="font-mono">{scopeId}</span>.
          </>
        }
      />

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader title="Departments" description="Create a department inside this faculty." />
          <CardBody className="space-y-3">
            <p className="text-sm text-ink-600 dark:text-ink-400">
              A department must belong to a faculty that exists — the check is made when you
              create it, so a typo cannot become a department hanging off nothing. You may only
              create inside your own faculty.
            </p>
            <Link
              to="../departments"
              className="inline-block text-sm font-medium text-brand-600 dark:text-brand-400"
            >
              Create a department →
            </Link>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Offer chains"
            description="Where a full programme overflows to, in preference order."
          />
          <CardBody className="space-y-3">
            <p className="text-sm text-ink-600 dark:text-ink-400">
              An alternative-programme chain spends <strong>other departments&rsquo;</strong>{' '}
              quota, which is why it is the faculty&rsquo;s to publish and not a
              department&rsquo;s: one department must not point at another&rsquo;s places
              unilaterally.
            </p>
            <Link
              to="../offer-chains"
              className="inline-block text-sm font-medium text-brand-600 dark:text-brand-400"
            >
              Publish a chain →
            </Link>
          </CardBody>
        </Card>
      </div>

      <Note tone="info" className="mt-6" title="Why there is no list of your departments">
        The API has no route that enumerates the departments in a faculty. Rather than keep a
        second copy of the structure in this app and let it drift, these pages ask you for the
        department id you mean.
      </Note>
    </>
  )
}
