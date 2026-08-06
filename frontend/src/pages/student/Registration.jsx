import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import PageHeader from '../../components/PageHeader'
import Badge from '../../components/ui/Badge'
import { Note } from '../../components/ui/Feedback'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import { useRegisterForCourse, wasAccepted } from '../../features/enrollment/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * Register for one course, and see exactly why not if you cannot.
 *
 * **There is no list of what you are registered for**, and that is a property of the API rather
 * than a shortcut here: Enrollment has exactly one inbound route, a POST. Showing a register
 * would mean assembling one from something, and there is nothing to assemble it from. A table
 * of invented rows would be worse than its absence.
 *
 * **A refusal is a 200.** It is a decision the university made about a request it understood,
 * and it carries *every* unmet reason rather than the first — a student refused for a missing
 * prerequisite, who sorts that out and is then refused for a full course, has queued twice for
 * information the university had both times. So the page lists them all.
 */
export default function Registration() {
  useTitle('Registration')
  const { scopeId, loginId } = useAuth()
  const mutation = useRegisterForCourse()

  const { values, bind } = useFields({
    enrollment_id: '',
    course_id: '',
    session_id: '',
    semester_id: '',
    semester_ordinal: '1',
  })

  const submit = () =>
    mutation.mutate({
      enrollmentId: values.enrollment_id,
      // Enrollment identifies a student by the id Billing's ledger also answers to — which is
      // the matric number after matriculation. `loginId` is that number.
      studentId: loginId,
      courseId: values.course_id,
      sessionId: values.session_id,
      semesterId: values.semester_id,
      semesterOrdinal: Number(values.semester_ordinal),
    })

  const outcome = mutation.data

  return (
    <>
      <PageHeader
        title="Course registration"
        description="One course at a time. Eligibility is checked when you submit."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-6">
          <FormCard
            title="Register for a course"
            submitLabel="Register"
            mutation={{ ...mutation, data: null }}
            onSubmit={submit}
            footNote={`Registering as ${loginId}. You may only register yourself.`}
          >
            <FieldRow>
              <Input
                label="Course"
                required
                placeholder="csc-101"
                {...bind('course_id')}
                hint="The course code from the catalogue."
              />
              <Input
                label="Registration reference"
                required
                placeholder="enr-0001"
                {...bind('enrollment_id')}
                hint="Your own reference for this registration."
              />
            </FieldRow>
            <FieldRow columns={3}>
              <Input label="Session" required placeholder="sess-2026-2027" {...bind('session_id')} />
              <Input label="Semester" required placeholder="sem-2026-1" {...bind('semester_id')} />
              <Select label="Which half" {...bind('semester_ordinal')}>
                <option value="1">First semester</option>
                <option value="2">Second semester</option>
              </Select>
            </FieldRow>
            <p className="hint">
              Which half of the session matters: fee clearance requires 70% of the session fee to
              register for the first semester, and all of it for the second.
            </p>
          </FormCard>

          {outcome && (
            <Card>
              <CardHeader
                title={wasAccepted(outcome) ? 'You are registered' : 'Not registered'}
                action={
                  <Badge tone={wasAccepted(outcome) ? 'success' : 'danger'}>
                    {wasAccepted(outcome) ? 'Accepted' : 'Refused'}
                  </Badge>
                }
              />
              <CardBody>
                {wasAccepted(outcome) ? (
                  <div className="space-y-3 text-sm">
                    <p className="text-ink-700 dark:text-ink-300">
                      <span className="font-mono">{outcome.course_id}</span> for{' '}
                      {outcome.term.label} — {outcome.credit_units} units
                      {outcome.is_carry_over && (
                        <Badge tone="warning" className="ml-2">
                          Carry-over
                        </Badge>
                      )}
                    </p>
                    <p className="hint">
                      {outcome.seats_remaining} seats left on this offering. Your credit units are
                      fixed at registration — a course later re-valued will not change this term.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <p className="text-sm text-ink-600 dark:text-ink-400">
                      Everything standing in the way, not just the first:
                    </p>
                    <ul className="space-y-2">
                      {outcome.reasons.map((reason) => (
                        <li
                          key={reason.reason}
                          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm dark:border-red-900 dark:bg-red-950/40"
                        >
                          <p className="font-medium text-red-900 dark:text-red-200">
                            {reason.reason}
                          </p>
                          <p className="mt-0.5 text-red-800/80 dark:text-red-300/80">
                            {reason.detail}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardBody>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Note tone="info" title="What is checked">
            <ul className="mt-1 list-inside list-disc space-y-1">
              <li>Prerequisites you have passed</li>
              <li>A cap of 24 credit units per semester</li>
              <li>Whether the offering has a seat left</li>
              <li>Financial clearance for this half of the session</li>
            </ul>
          </Note>
          <Note tone="warning" title="No drop or withdraw">
            A registration cannot be undone from here. When and how a course may be dropped is not
            something the system has been told, so it does not pretend to offer it.
          </Note>
        </div>
      </div>
    </>
  )
}
