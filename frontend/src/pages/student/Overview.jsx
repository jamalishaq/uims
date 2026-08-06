import { Link } from 'react-router-dom'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import PageHeader, { Detail, StatTile } from '../../components/PageHeader'
import { StatusBadge } from '../../components/ui/Badge'
import { Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { useStudent } from '../../features/studentProfile/queries'
import { useAcademicRecord } from '../../features/academicRecords/queries'
import { useAccount } from '../../features/billing/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * The student's home, composed from three contexts by the client.
 *
 * That composition is this page's whole reason for existing, and it is deliberately here rather
 * than on the server. Student Profile is the identity anchor and stays thin — a read over there
 * that assembled a profile, a transcript and a ledger would be one module knowing four contexts,
 * which only the composition root may be. A client may, so the client does: three queries, side
 * by side.
 *
 * Each panel fails on its own. A student with no academic record is a **fresher**, not an
 * error, and a ledger that 404s is an account not yet opened — so neither takes the page down.
 */
export default function StudentOverview() {
  useTitle('Overview')
  const { scopeId, loginId } = useAuth()

  const student = useStudent(scopeId)
  // Academic Records keys a record by the id Enrollment and Billing also use, which is the
  // **matric number** — `loginId` — not the `student_id` Student Profile minted. Verified
  // against the running API: /records/stu-0001 is a 404 and /records/260591001 is the record.
  const record = useAcademicRecord(loginId)
  // The ledger is keyed by a neutral party-id: the matric number after matriculation, the
  // applicant id before it. `loginId` is the matric number, which is the one this app holds.
  const account = useAccount(loginId)

  return (
    <>
      <PageHeader
        title={student.data ? student.data.full_name : 'Overview'}
        description="Your record, your registration standing and your ledger."
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Matric number"
          value={<span className="font-mono text-lg">{loginId}</span>}
          caption="Issued at matriculation. It never changes."
        />
        <StatTile
          label="CGPA"
          value={record.data?.cgpa ?? '—'}
          caption={record.data ? `over ${record.data.total_units} units` : 'No grades recorded yet'}
          tone={record.data?.standing === 'probation' ? 'danger' : 'neutral'}
        />
        <StatTile
          label="Standing"
          value={record.data ? <StatusBadge status={record.data.standing} /> : '—'}
          caption="Judged on the reported CGPA."
        />
        <StatTile
          label="Outstanding"
          value={account.data ? `₦${account.data.outstanding}` : '—'}
          caption={account.data ? `${account.data.charges.length} charges on file` : 'No ledger yet'}
          tone={account.data && account.data.outstanding !== '0.00' ? 'warning' : 'success'}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Your record" />
          {student.isLoading ? (
            <Loading />
          ) : student.data ? (
            <CardBody>
              <dl>
                <Detail label="Full name" value={student.data.full_name} />
                <Detail label="Matric number" value={student.data.matric_number} mono />
                <Detail label="Programme" value={student.data.program_id} mono />
                <Detail label="Entry session" value={student.data.entry_session_id} mono />
                <Detail label="Level" value={student.data.entry_level} />
                <Detail label="Email" value={student.data.email} />
                <Detail label="Phone" value={student.data.phone_number} />
              </dl>
              <p className="mt-4 hint">
                Something wrong here? Corrections are made by the registry, not from this page —
                a record somebody can rewrite about themselves is not a record.
              </p>
            </CardBody>
          ) : (
            <EmptyState
              title="No student record"
              description="Nothing is stored against this id yet. If you have just been matriculated, the registry may still be issuing your number."
            />
          )}
        </Card>

        <Card>
          <CardHeader
            title="Academic standing"
            action={
              <Link
                to="../transcript"
                className="text-sm font-medium text-brand-600 dark:text-brand-400"
              >
                Full transcript
              </Link>
            }
          />
          {record.isLoading ? (
            <Loading />
          ) : record.data ? (
            <CardBody className="space-y-4">
              <dl>
                <Detail label="CGPA" value={record.data.cgpa} mono />
                <Detail label="Units attempted" value={record.data.total_units} />
                <Detail label="Courses passed" value={record.data.passed_course_ids.length} />
                <Detail
                  label="Standing"
                  value={<StatusBadge status={record.data.standing} />}
                />
              </dl>
              {record.data.standing === 'probation' && (
                <Note tone="warning" title="You are on probation">
                  Your CGPA is below the 1.50 threshold. Registration is not blocked by this, but
                  speak to your department.
                </Note>
              )}
            </CardBody>
          ) : (
            <EmptyState
              title="No grades yet"
              description="A record is created the first time a lecturer submits a grade for you. Having none is normal in your first semester."
            />
          )}
        </Card>
      </div>
    </>
  )
}
