import { useState } from 'react'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import Button from '../../components/ui/Button'
import PageHeader from '../../components/PageHeader'
import Badge, { humanise } from '../../components/ui/Badge'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import {
  useAmendLecturerProfile,
  useAssignLecturerToCourse,
  useDepartmentLecturers,
  useRegisterLecturer,
  useWithdrawLecturerFromCourse,
} from '../../features/facultyDepartment/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * The confirmed ladder and terms — the server's own wire values, not this app's labels.
 *
 * An unrecognised rank is a 422 rather than a silently dropped field, so these have to match
 * exactly. `humanise` handles the display; the `value` is what crosses.
 */
const RANKS = [
  'professor',
  'reader',
  'senior lecturer',
  'lecturer I',
  'lecturer II',
  'assistant lecturer',
  'graduate assistant',
]

const EMPLOYMENT = ['full-time', 'part-time', 'visiting', 'adjunct', 'contract', 'sabbatical']

/**
 * Departmental staff: who they are, and what they teach.
 *
 * The **course assignments** half is the one that matters operationally. Grade submission is
 * authorised against exactly these, so a lecturer with no assignment cannot submit anything —
 * and the refusal they get says nothing about why. The list flags them.
 */
export default function Lecturers() {
  useTitle('Lecturers')
  const { scopeId } = useAuth()
  const lecturers = useDepartmentLecturers(scopeId)
  const register = useRegisterLecturer()

  const { values, bind, reset } = useFields({ lecturer_id: '', full_name: '' })

  return (
    <>
      <PageHeader
        title="Lecturers"
        description="Staff records, and the courses each is authorised to grade."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          {lecturers.isLoading ? (
            <Loading />
          ) : lecturers.error ? (
            <ErrorNote error={lecturers.error} />
          ) : lecturers.data.lecturers.length === 0 ? (
            <Card>
              <EmptyState
                title="No staff registered"
                description="Register one alongside. They will teach nothing until a course is assigned."
              />
            </Card>
          ) : (
            lecturers.data.lecturers.map((lecturer) => (
              <LecturerCard key={lecturer.lecturer_id} lecturer={lecturer} />
            ))
          )}
        </div>

        <div className="space-y-6">
          <FormCard
            title="Register a lecturer"
            submitLabel="Register"
            mutation={register}
            onSubmit={() =>
              register.mutate(
                { ...values, department_id: scopeId },
                { onSuccess: () => reset() }
              )
            }
            successTitle="Lecturer registered"
            renderSuccess={(lecturer) => (
              <span>
                <span className="font-mono">{lecturer.lecturer_id}</span> — teaching nothing yet.
              </span>
            )}
            footNote={`Registered into ${scopeId}. You may only register into your own department.`}
          >
            <Input label="Staff id" required placeholder="lec-001" {...bind('lecturer_id')} />
            <Input label="Full name" required {...bind('full_name')} />
          </FormCard>

          <Note tone="info" title="Rank is not required">
            A staff record with no rank means nobody has recorded one, which is a real and common
            state. There is no default, deliberately — a record standing at Lecturer II would read
            identically to one somebody actually checked.
          </Note>
        </div>
      </div>
    </>
  )
}

function LecturerCard({ lecturer }) {
  const [open, setOpen] = useState(false)
  const amend = useAmendLecturerProfile()
  const assign = useAssignLecturerToCourse()
  const withdraw = useWithdrawLecturerFromCourse()

  const profile = useFields({
    rank: lecturer.rank ?? '',
    employment_status: lecturer.employment_status ?? '',
  })
  const assignment = useFields({ course_id: '', session_id: '' })

  return (
    <Card>
      <CardHeader
        title={lecturer.full_name}
        description={lecturer.lecturer_id}
        action={
          <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)}>
            {open ? 'Close' : 'Manage'}
          </Button>
        }
      />
      <CardBody className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={lecturer.rank ? 'brand' : 'neutral'}>
            {lecturer.rank ? humanise(lecturer.rank) : 'Rank not recorded'}
          </Badge>
          <Badge tone={lecturer.employment_status ? 'brand' : 'neutral'}>
            {lecturer.employment_status
              ? humanise(lecturer.employment_status)
              : 'Employment not recorded'}
          </Badge>
          <Badge tone={lecturer.assignments.length > 0 ? 'success' : 'warning'}>
            {lecturer.assignments.length} course
            {lecturer.assignments.length === 1 ? '' : 's'}
          </Badge>
        </div>

        {lecturer.assignments.length === 0 && (
          <p className="text-xs text-amber-700 dark:text-amber-400">
            Teaches nothing — every grade they submit will be refused.
          </p>
        )}

        {open && (
          <div className="space-y-5 border-t border-ink-200 pt-4 dark:border-ink-800">
            <section>
              <h3 className="mb-2 text-sm font-semibold text-ink-900 dark:text-ink-100">
                Course assignments
              </h3>
              <div className="mb-3 space-y-2">
                {lecturer.assignments.map((a) => (
                  <div
                    key={`${a.course_id}-${a.session_id}`}
                    className="flex items-center justify-between gap-3 rounded-lg bg-ink-50 px-3 py-2 text-sm dark:bg-ink-800/60"
                  >
                    <span className="font-mono">
                      {a.course_id} · {a.session_id}
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={withdraw.isPending}
                      onClick={() =>
                        withdraw.mutate({
                          lecturerId: lecturer.lecturer_id,
                          courseId: a.course_id,
                          sessionId: a.session_id,
                        })
                      }
                    >
                      Withdraw
                    </Button>
                  </div>
                ))}
              </div>
              <FieldRow>
                <Input label="Course" placeholder="csc-101" {...assignment.bind('course_id')} />
                <Input
                  label="Session"
                  placeholder="sess-2026-2027"
                  {...assignment.bind('session_id')}
                />
              </FieldRow>
              <Button
                size="sm"
                className="mt-3"
                loading={assign.isPending}
                onClick={() =>
                  assign.mutate({
                    lecturerId: lecturer.lecturer_id,
                    courseId: assignment.values.course_id,
                    sessionId: assignment.values.session_id,
                  })
                }
              >
                Assign course
              </Button>
              <p className="mt-2 hint">
                The course code is not checked against the catalogue. A typo surfaces later, when
                Academic Records refuses a course it has no credit units for.
              </p>
              <ErrorNote error={assign.error ?? withdraw.error} className="mt-3" />
            </section>

            <section>
              <h3 className="mb-2 text-sm font-semibold text-ink-900 dark:text-ink-100">
                Staff record
              </h3>
              <FieldRow>
                <Select label="Rank" {...profile.bind('rank')}>
                  <option value="">Not recorded</option>
                  {RANKS.map((rank) => (
                    <option key={rank} value={rank}>
                      {humanise(rank)}
                    </option>
                  ))}
                </Select>
                <Select label="Employment" {...profile.bind('employment_status')}>
                  <option value="">Not recorded</option>
                  {EMPLOYMENT.map((status) => (
                    <option key={status} value={status}>
                      {humanise(status)}
                    </option>
                  ))}
                </Select>
              </FieldRow>
              <Button
                size="sm"
                className="mt-3"
                loading={amend.isPending}
                onClick={() =>
                  amend.mutate({
                    lecturerId: lecturer.lecturer_id,
                    rank: profile.values.rank || null,
                    employment_status: profile.values.employment_status || null,
                    // Sent explicitly, because this replaces rather than patches: omitting it
                    // would clear the qualifications already on the record.
                    qualifications: lecturer.qualifications,
                  })
                }
              >
                Save record
              </Button>
              <p className="mt-2 hint">
                Saving replaces the record wholesale. Clearing a field here clears it on the
                record — it is a form being saved, not a promotion, and no history is kept.
              </p>
              <ErrorNote error={amend.error} className="mt-3" />
            </section>
          </div>
        )}
      </CardBody>
    </Card>
  )
}
