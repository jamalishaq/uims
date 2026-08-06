import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import PageHeader from '../../components/PageHeader'
import { Note } from '../../components/ui/Feedback'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import { useLecturer, useSubmitGrade } from '../../features/facultyDepartment/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * Submit one mark.
 *
 * **The score is the raw mark out of 100, and nothing else.** No letter, no grade point: what a
 * mark is worth is Academic Records' grading scale, and a form that offered a letter would be
 * this part of the system forming an opinion about a scale it does not own.
 *
 * **Submitting publishes.** By the time this returns, Academic Records has already consumed the
 * event and the transcript line exists — the bus is synchronous and a subscriber's failure is
 * not swallowed. So a success here means the mark is on the transcript, not that it is queued,
 * and the page says so rather than implying a delay.
 *
 * The course dropdown is built from this lecturer's own assignments, because those are what the
 * server authorizes against. Offering a free-text course would let somebody type one they do not
 * teach and be refused for a reason the form could have prevented.
 */
export default function SubmitGrade() {
  useTitle('Submit a grade')
  const { scopeId } = useAuth()
  const { data: lecturer } = useLecturer(scopeId)
  const mutation = useSubmitGrade()

  const assignments = lecturer?.assignments ?? []
  const { values, bind } = useFields({
    assignment: '',
    student_id: '',
    semester_id: '',
    score: '',
  })

  const submit = () => {
    const [course_id, session_id] = values.assignment.split('@@')
    mutation.mutate({
      lecturer_id: scopeId,
      session_id,
      course_id,
      student_id: values.student_id,
      semester_id: values.semester_id,
      score: Number(values.score),
    })
  }

  return (
    <>
      <PageHeader
        title="Submit a grade"
        description="One student, one course, one mark out of 100."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <FormCard
          title="Mark"
          submitLabel="Submit grade"
          mutation={mutation}
          onSubmit={submit}
          successTitle="Recorded on the transcript"
          renderSuccess={(grade) => (
            <span>
              <span className="font-mono">{grade.course_id}</span> for{' '}
              <span className="font-mono">{grade.student_id}</span> — {grade.score}. This is
              already on their academic record.
            </span>
          )}
          footNote="Submitting as yourself. A grade cannot be submitted on another lecturer's behalf."
        >
          <Select
            label="Course"
            required
            {...bind('assignment')}
            hint="Only the courses you are assigned to. The server checks this again."
          >
            <option value="">Select a course…</option>
            {assignments.map((assignment) => (
              <option
                key={`${assignment.course_id}-${assignment.session_id}`}
                value={`${assignment.course_id}@@${assignment.session_id}`}
              >
                {assignment.course_id} — {assignment.session_id}
              </option>
            ))}
          </Select>

          <FieldRow>
            <Input
              label="Student"
              required
              placeholder="260591001"
              {...bind('student_id')}
              hint="Their matric number."
            />
            <Input
              label="Semester"
              required
              placeholder="sem-2026-1"
              {...bind('semester_id')}
            />
          </FieldRow>

          <Input
            label="Score"
            type="number"
            min={0}
            max={100}
            required
            {...bind('score')}
            hint="The raw mark. The letter and grade point are derived by the grading scale."
          />
        </FormCard>

        <div className="space-y-4">
          <Note tone="warning" title="A submitted grade is final">
            Once recorded it cannot be resubmitted with a different score. Changing it is a
            correction, which the registry makes and which leaves an audit entry naming a reason
            and an authoriser.
          </Note>
          <Note tone="info" title="It takes effect immediately">
            Academic Records consumes the submission before this request returns. There is no
            queue and no delay — the CGPA changes as soon as you see the confirmation.
          </Note>
          {assignments.length === 0 && (
            <Note tone="danger" title="You have no course assignments">
              Every submission will be refused until your department assigns you a course.
            </Note>
          )}
        </div>
      </div>
    </>
  )
}
