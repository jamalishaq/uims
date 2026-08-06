import { Link } from 'react-router-dom'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import PageHeader, { Detail, StatTile } from '../../components/PageHeader'
import Badge, { humanise } from '../../components/ui/Badge'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { useLecturer } from '../../features/facultyDepartment/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * A lecturer's own staff record and what they are assigned to teach.
 *
 * The assignments matter more than they look: **they are what makes grade submission possible
 * at all.** `SubmitGrade` authorizes against exactly this list, so a lecturer with none can
 * reach the grade form and be refused by every course they try. Showing the list first, with
 * that stated, is the difference between an understandable refusal and a bug report.
 *
 * `rank` and `employment_status` come back `null` when nobody has recorded them. That is a real
 * state and the page says "not recorded" rather than inventing a default — a record standing at
 * Lecturer II would read identically to one somebody actually checked.
 */
export default function LecturerOverview() {
  useTitle('Overview')
  const { scopeId } = useAuth()
  const { data: lecturer, isLoading, error } = useLecturer(scopeId)

  if (isLoading) return <Loading label="Loading your record…" />

  if (error) {
    return (
      <>
        <PageHeader title="Overview" />
        <ErrorNote error={error} title="Could not read your staff record" />
      </>
    )
  }

  const sessions = new Set(lecturer.assignments.map((a) => a.session_id))

  return (
    <>
      <PageHeader
        title={lecturer.full_name}
        description="Your staff record, and the courses you may submit grades for."
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatTile
          label="Course assignments"
          value={lecturer.assignments.length}
          caption="Across all sessions"
          tone={lecturer.assignments.length === 0 ? 'warning' : 'neutral'}
        />
        <StatTile label="Sessions" value={sessions.size} />
        <StatTile label="Qualifications" value={lecturer.qualifications.length} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Staff record" />
          <CardBody>
            <dl>
              <Detail label="Staff id" value={lecturer.lecturer_id} mono />
              <Detail label="Department" value={lecturer.department_id} mono />
              <Detail
                label="Rank"
                value={
                  lecturer.rank ? (
                    humanise(lecturer.rank)
                  ) : (
                    <span className="font-normal text-ink-400">Not recorded</span>
                  )
                }
              />
              <Detail
                label="Employment"
                value={
                  lecturer.employment_status ? (
                    humanise(lecturer.employment_status)
                  ) : (
                    <span className="font-normal text-ink-400">Not recorded</span>
                  )
                }
              />
            </dl>
            <p className="mt-4 hint">
              Blank fields mean nobody has recorded them, not that they are unknown to you. Your
              department registry maintains this record.
            </p>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Qualifications"
            description="Kept as a list; amending replaces it wholesale."
          />
          {lecturer.qualifications.length === 0 ? (
            <EmptyState
              title="None recorded"
              description="Your department registry can add them."
            />
          ) : (
            <CardBody className="space-y-2">
              {lecturer.qualifications.map((held, index) => (
                <div
                  key={index}
                  className="border-b border-ink-100 py-2.5 text-sm last:border-0 dark:border-ink-800"
                >
                  <p className="font-medium text-ink-900 dark:text-ink-100">
                    {held.degree}
                    {held.discipline ? `, ${held.discipline}` : ''}
                  </p>
                  <p className="hint">
                    {[held.institution, held.year].filter(Boolean).join(' · ') || '—'}
                  </p>
                </div>
              ))}
            </CardBody>
          )}
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Courses you teach"
          description="Grade submission is authorised against this list, and nothing else."
          action={
            lecturer.assignments.length > 0 && (
              <Link
                to="../grades"
                className="text-sm font-medium text-brand-600 dark:text-brand-400"
              >
                Submit a grade
              </Link>
            )
          }
        />
        {lecturer.assignments.length === 0 ? (
          <CardBody>
            <Note tone="warning" title="You are not assigned to any course">
              Until your department assigns you one, every grade you try to submit will be
              refused — the check is on the assignment, not on your role.
            </Note>
          </CardBody>
        ) : (
          <CardBody className="flex flex-wrap gap-2">
            {lecturer.assignments.map((assignment) => (
              <Badge key={`${assignment.course_id}-${assignment.session_id}`} tone="brand">
                <span className="font-mono">{assignment.course_id}</span>
                <span className="ml-1.5 opacity-70">{assignment.session_id}</span>
              </Badge>
            ))}
          </CardBody>
        )}
      </Card>
    </>
  )
}
