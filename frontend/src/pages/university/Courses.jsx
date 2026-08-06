import { useState } from 'react'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Button from '../../components/ui/Button'
import PageHeader from '../../components/PageHeader'
import Badge from '../../components/ui/Badge'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import {
  useAddPrerequisite,
  useDepartmentCourses,
  usePrerequisiteChain,
  useRegisterCourse,
  useReinstateCourse,
  useRemovePrerequisite,
  useRetireCourse,
} from '../../features/courseCatalog/queries'
import useTitle from '../../hooks/useTitle'

/**
 * The catalogue: courses, their credit units, and their prerequisite chains.
 *
 * **Retiring is a state, not a delete.** A retired course must keep resolving, because
 * transcripts refer to courses no longer taught — so it stays in the catalogue and comes back
 * behind the "include retired" toggle rather than disappearing.
 *
 * **A course's credit units are snapshotted at registration and at grading.** Changing them
 * here does not rewrite a term already registered or a transcript already issued, which is
 * exactly what makes amending safe.
 */
export default function Courses() {
  useTitle('Courses')
  const [departmentId, setDepartmentId] = useState('')
  const [browsing, setBrowsing] = useState('')
  const [includeRetired, setIncludeRetired] = useState(false)

  const courses = useDepartmentCourses(browsing, includeRetired)
  const register = useRegisterCourse()
  const retire = useRetireCourse()
  const reinstate = useReinstateCourse()

  const { values, bind, reset } = useFields({
    course_id: '',
    department_id: '',
    code: '',
    title: '',
    credit_units: '',
  })

  return (
    <>
      <PageHeader
        title="Course catalogue"
        description="Slow-changing reference data. It has no notion of a specific student."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <Card>
            <CardHeader
              title="Browse a department's courses"
              action={
                <label className="flex items-center gap-2 text-sm text-ink-600 dark:text-ink-400">
                  <input
                    type="checkbox"
                    checked={includeRetired}
                    onChange={(e) => setIncludeRetired(e.target.checked)}
                    className="rounded border-ink-300"
                  />
                  Include retired
                </label>
              }
            />
            <CardBody>
              <form
                className="flex items-end gap-3"
                onSubmit={(event) => {
                  event.preventDefault()
                  setBrowsing(departmentId.trim())
                }}
              >
                <Input
                  label="Department id"
                  className="flex-1"
                  required
                  placeholder="dept-csc"
                  value={departmentId}
                  onChange={(e) => setDepartmentId(e.target.value)}
                />
                <Button type="submit">List</Button>
              </form>

              {browsing && (
                <div className="mt-5 border-t border-ink-200 pt-4 dark:border-ink-800">
                  {courses.isLoading ? (
                    <Loading />
                  ) : courses.error ? (
                    <ErrorNote error={courses.error} />
                  ) : courses.data.courses.length === 0 ? (
                    <EmptyState
                      title="No courses"
                      description="No courses here — or no such department. Both answer the same."
                    />
                  ) : (
                    <div className="space-y-3">
                      {courses.data.courses.map((course) => (
                        <CourseRow
                          key={course.course_id}
                          course={course}
                          onRetire={() => retire.mutate(course.course_id)}
                          onReinstate={() => reinstate.mutate(course.course_id)}
                          busy={retire.isPending || reinstate.isPending}
                        />
                      ))}
                      <ErrorNote error={retire.error ?? reinstate.error} />
                    </div>
                  )}
                </div>
              )}
            </CardBody>
          </Card>
        </div>

        <div className="space-y-6">
          <FormCard
            title="Register a course"
            submitLabel="Register course"
            mutation={register}
            onSubmit={() =>
              register.mutate(
                { ...values, credit_units: Number(values.credit_units) },
                { onSuccess: reset }
              )
            }
            successTitle="Course registered"
          >
            <FieldRow>
              <Input label="Course id" required placeholder="csc-101" {...bind('course_id')} />
              <Input label="Code" required placeholder="CSC101" {...bind('code')} />
            </FieldRow>
            <Input label="Title" required {...bind('title')} />
            <FieldRow>
              <Input
                label="Department id"
                required
                placeholder="dept-csc"
                {...bind('department_id')}
              />
              <Input
                label="Credit units"
                type="number"
                min={1}
                required
                {...bind('credit_units')}
              />
            </FieldRow>
          </FormCard>

          <Note tone="info" title="Amending units is safe">
            Credit units are snapshotted when a student registers and again when a grade is
            recorded. Changing them here does not rewrite a term already registered or a
            transcript already issued.
          </Note>
        </div>
      </div>
    </>
  )
}

function CourseRow({ course, onRetire, onReinstate, busy }) {
  const [open, setOpen] = useState(false)
  const chain = usePrerequisiteChain(open ? course.course_id : null)
  const add = useAddPrerequisite()
  const remove = useRemovePrerequisite()
  const [prerequisiteId, setPrerequisiteId] = useState('')

  return (
    <div className="rounded-lg border border-ink-200 px-4 py-3 dark:border-ink-800">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-ink-900 dark:text-ink-100">
            <span className="font-mono">{course.code}</span> — {course.title}
          </p>
          <p className="font-mono hint">
            {course.course_id} · {course.credit_units} units
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={course.is_active ? 'success' : 'neutral'}>
            {course.is_active ? 'Active' : 'Retired'}
          </Badge>
          <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)}>
            {open ? 'Close' : 'Prerequisites'}
          </Button>
          <Button
            size="sm"
            variant={course.is_active ? 'secondary' : 'primary'}
            loading={busy}
            onClick={course.is_active ? onRetire : onReinstate}
          >
            {course.is_active ? 'Retire' : 'Reinstate'}
          </Button>
        </div>
      </div>

      {open && (
        <div className="mt-4 space-y-3 border-t border-ink-200 pt-3 dark:border-ink-800">
          <div>
            <p className="hint">Direct prerequisites</p>
            {course.prerequisite_ids.length === 0 ? (
              <p className="text-sm text-ink-500">None.</p>
            ) : (
              <div className="mt-1 flex flex-wrap gap-2">
                {course.prerequisite_ids.map((id) => (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1.5 rounded-full bg-ink-100 px-2.5 py-1 text-xs dark:bg-ink-800"
                  >
                    <span className="font-mono">{id}</span>
                    <button
                      type="button"
                      aria-label={`Remove ${id}`}
                      className="text-ink-500 hover:text-red-600"
                      onClick={() =>
                        remove.mutate({ courseId: course.course_id, prerequisiteId: id })
                      }
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {chain.data && chain.data.prerequisite_ids.length > 0 && (
            <div>
              <p className="hint">
                Everything that must be passed first, transitively
              </p>
              <p className="mt-1 font-mono text-sm text-ink-700 dark:text-ink-300">
                {chain.data.prerequisite_ids.join(' · ')}
              </p>
            </div>
          )}

          <div className="flex items-end gap-2">
            <Input
              label="Add a prerequisite"
              className="flex-1"
              placeholder="csc-100"
              value={prerequisiteId}
              onChange={(e) => setPrerequisiteId(e.target.value)}
            />
            <Button
              size="sm"
              loading={add.isPending}
              onClick={() =>
                add.mutate(
                  { courseId: course.course_id, prerequisiteId: prerequisiteId.trim() },
                  { onSuccess: () => setPrerequisiteId('') }
                )
              }
            >
              Add
            </Button>
          </div>
          <p className="hint">A prerequisite that would form a cycle is refused.</p>
          <ErrorNote error={add.error ?? remove.error} />
        </div>
      )}
    </div>
  )
}
