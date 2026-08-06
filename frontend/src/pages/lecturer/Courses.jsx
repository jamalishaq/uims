import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import PageHeader from '../../components/PageHeader'
import Badge from '../../components/ui/Badge'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { useLecturer } from '../../features/facultyDepartment/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * The courses this lecturer is assigned to, grouped by session.
 *
 * **No student lists and no class registers.** Enrollment has one inbound route — a POST to
 * register — so there is no way to ask who is registered for a course. A page that showed a
 * class list would be showing something invented. Where a lecturer needs a student's id to
 * submit a mark, they have it from the department.
 */
export default function LecturerCourses() {
  useTitle('My courses')
  const { scopeId } = useAuth()
  const { data: lecturer, isLoading, error } = useLecturer(scopeId)

  if (isLoading) return <Loading />
  if (error) return <ErrorNote error={error} title="Could not read your assignments" />

  const bySession = lecturer.assignments.reduce((groups, assignment) => {
    ;(groups[assignment.session_id] ??= []).push(assignment)
    return groups
  }, {})

  return (
    <>
      <PageHeader
        title="My courses"
        description="What you are assigned to teach, and may therefore grade."
      />

      {lecturer.assignments.length === 0 ? (
        <EmptyState
          title="No course assignments"
          description="Your department registry assigns courses. Until one is assigned, grade submission will be refused for every course you try."
        />
      ) : (
        <div className="space-y-6">
          {Object.entries(bySession).map(([sessionId, assignments]) => (
            <Card key={sessionId}>
              <CardHeader
                title={sessionId}
                description={`${assignments.length} ${assignments.length === 1 ? 'course' : 'courses'}`}
              />
              <CardBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {assignments.map((assignment) => (
                  <div
                    key={assignment.course_id}
                    className="rounded-lg border border-ink-200 px-4 py-3 dark:border-ink-800"
                  >
                    <p className="font-mono text-sm font-medium text-ink-900 dark:text-ink-100">
                      {assignment.course_id}
                    </p>
                    <Badge tone="success" className="mt-2">
                      Assigned
                    </Badge>
                  </div>
                ))}
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      <Note tone="info" className="mt-6" title="Why there is no class list">
        There is no route that returns who is registered for a course — Enrollment records
        registrations and does not publish a register. Rather than invent one, this page shows
        only what the system actually holds.
      </Note>
    </>
  )
}
