import { Link } from 'react-router-dom'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import PageHeader, { StatTile } from '../../components/PageHeader'
import Badge from '../../components/ui/Badge'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import {
  useDepartmentLecturers,
  useDepartmentPrograms,
} from '../../features/facultyDepartment/queries'
import { useDepartmentCourses } from '../../features/courseCatalog/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * What this department holds: its programmes, its staff and its courses.
 *
 * All three reads are keyed by the department id in the signed-in principal's scope, which is
 * the only starting point available — nothing enumerates departments, and nothing needs to,
 * because a registrar is scoped to exactly one.
 */
export default function DepartmentOverview() {
  useTitle('Overview')
  const { scopeId } = useAuth()

  const programs = useDepartmentPrograms(scopeId)
  const lecturers = useDepartmentLecturers(scopeId)
  const courses = useDepartmentCourses(scopeId)

  const admitting = programs.data?.programs.filter((p) => p.is_admitting).length ?? 0
  const unassigned =
    lecturers.data?.lecturers.filter((l) => l.assignments.length === 0).length ?? 0

  return (
    <>
      <PageHeader
        title="Department"
        description={
          <>
            Everything below is scoped to <span className="font-mono">{scopeId}</span>.
          </>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile
          label="Programmes"
          value={programs.data?.programs.length ?? '—'}
          caption={`${admitting} taking applications`}
        />
        <StatTile label="Lecturers" value={lecturers.data?.lecturers.length ?? '—'} />
        <StatTile
          label="Unassigned staff"
          value={unassigned}
          caption="Cannot submit grades until assigned"
          tone={unassigned > 0 ? 'warning' : 'success'}
        />
        <StatTile label="Courses" value={courses.data?.courses.length ?? '—'} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Programmes"
            action={
              <Link
                to="../programmes"
                className="text-sm font-medium text-brand-600 dark:text-brand-400"
              >
                Manage
              </Link>
            }
          />
          {programs.isLoading ? (
            <Loading />
          ) : programs.error ? (
            <CardBody>
              <ErrorNote error={programs.error} />
            </CardBody>
          ) : programs.data.programs.length === 0 ? (
            <EmptyState
              title="No programmes"
              description="This department has none yet. A programme is created not admitting."
            />
          ) : (
            <CardBody className="space-y-2">
              {programs.data.programs.map((program) => (
                <div
                  key={program.program_id}
                  className="flex items-center justify-between gap-4 border-b border-ink-100 py-2.5 last:border-0 dark:border-ink-800"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink-900 dark:text-ink-100">
                      {program.name}
                    </p>
                    <p className="font-mono hint">{program.program_id}</p>
                  </div>
                  <Badge tone={program.is_admitting ? 'success' : 'neutral'}>
                    {program.is_admitting ? 'Admitting' : 'Closed'}
                  </Badge>
                </div>
              ))}
            </CardBody>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Lecturers"
            action={
              <Link
                to="../lecturers"
                className="text-sm font-medium text-brand-600 dark:text-brand-400"
              >
                Manage
              </Link>
            }
          />
          {lecturers.isLoading ? (
            <Loading />
          ) : lecturers.data?.lecturers.length === 0 ? (
            <EmptyState title="No staff" description="Nobody is registered to this department." />
          ) : (
            <CardBody className="space-y-2">
              {(lecturers.data?.lecturers ?? []).map((lecturer) => (
                <div
                  key={lecturer.lecturer_id}
                  className="flex items-center justify-between gap-4 border-b border-ink-100 py-2.5 last:border-0 dark:border-ink-800"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink-900 dark:text-ink-100">
                      {lecturer.full_name}
                    </p>
                    <p className="font-mono hint">{lecturer.lecturer_id}</p>
                  </div>
                  <Badge tone={lecturer.assignments.length > 0 ? 'brand' : 'warning'}>
                    {lecturer.assignments.length} course
                    {lecturer.assignments.length === 1 ? '' : 's'}
                  </Badge>
                </div>
              ))}
            </CardBody>
          )}
        </Card>
      </div>

      {unassigned > 0 && (
        <Note tone="warning" className="mt-6" title={`${unassigned} lecturer(s) teach nothing`}>
          Grade submission is authorised against course assignments. Until one is assigned, every
          grade they submit is refused — and the refusal will look to them like a permissions bug.
        </Note>
      )}
    </>
  )
}
