import { useState } from 'react'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import Button from '../../components/ui/Button'
import PageHeader, { Detail } from '../../components/PageHeader'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import { useFindStudent, useRegisterStudent } from '../../features/studentProfile/queries'
import { useDepartmentPrograms } from '../../features/facultyDepartment/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * Look a student up, or register one by hand.
 *
 * **There is no student list.** Student Profile has no route that enumerates students, and this
 * page does not fake one — a registrar looks somebody up by a number they were given. The two
 * numbers that work are the matric number and the applicant id; the latter is how you follow a
 * matriculation to the student it produced, since nothing is published back to Admissions.
 *
 * The manual registration path exists for a student who never went through Admissions. **The
 * matric number is not an input** and cannot be: it is composed from the department's numeric
 * code and the entry year against a counter that survives restarts, precisely so two students
 * never share one.
 */
export default function DepartmentStudents() {
  useTitle('Students')
  const { scopeId } = useAuth()
  const programs = useDepartmentPrograms(scopeId)

  const [lookupBy, setLookupBy] = useState('matric_number')
  const [lookupValue, setLookupValue] = useState('')
  const [submitted, setSubmitted] = useState(null)

  const found = useFindStudent(
    submitted
      ? submitted.by === 'matric_number'
        ? { matricNumber: submitted.value }
        : { applicantId: submitted.value }
      : {}
  )

  const register = useRegisterStudent()
  const { values, bind, reset } = useFields({
    student_id: '',
    program_id: '',
    entry_session_id: '',
    full_name: '',
    email: '',
    phone_number: '',
    applicant_id: '',
  })

  return (
    <>
      <PageHeader title="Students" description="Look one up, or register one by hand." />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <Card>
            <CardHeader
              title="Find a student"
              description="By the matric number they hold, or the applicant id they applied under."
            />
            <CardBody>
              <form
                className="space-y-4"
                onSubmit={(event) => {
                  event.preventDefault()
                  setSubmitted({ by: lookupBy, value: lookupValue.trim() })
                }}
              >
                <FieldRow>
                  <Select
                    label="Search by"
                    value={lookupBy}
                    onChange={(e) => setLookupBy(e.target.value)}
                  >
                    <option value="matric_number">Matric number</option>
                    <option value="applicant_id">Applicant id</option>
                  </Select>
                  <Input
                    label="Value"
                    required
                    value={lookupValue}
                    onChange={(e) => setLookupValue(e.target.value)}
                    placeholder={lookupBy === 'matric_number' ? '260591001' : 'app-0001'}
                  />
                </FieldRow>
                <Button type="submit">Find</Button>
              </form>

              {submitted && (
                <div className="mt-5 border-t border-ink-200 pt-4 dark:border-ink-800">
                  {found.isLoading ? (
                    <Loading />
                  ) : found.error ? (
                    <EmptyState
                      title="No student matches that"
                      description="A number nobody holds reads the same as a number that is not a matric number at all — both are simply nobody."
                    />
                  ) : found.data ? (
                    <dl>
                      <Detail label="Name" value={found.data.full_name} />
                      <Detail label="Matric number" value={found.data.matric_number} mono />
                      <Detail label="Student id" value={found.data.student_id} mono />
                      <Detail label="Programme" value={found.data.program_id} mono />
                      <Detail label="Entry session" value={found.data.entry_session_id} mono />
                      <Detail label="Level" value={found.data.entry_level} />
                      <Detail label="Applicant id" value={found.data.applicant_id} mono />
                      <Detail label="Email" value={found.data.email} />
                      <Detail label="Phone" value={found.data.phone_number} />
                    </dl>
                  ) : null}
                </div>
              )}
            </CardBody>
          </Card>

          <Note tone="info" title="No level changes here">
            Nothing on this page moves a student's level. What advances one and when has never
            been stated to the system, so it does not offer a control that would have to invent
            a rule.
          </Note>
        </div>

        <FormCard
          title="Register a student by hand"
          description="For somebody who never went through Admissions."
          submitLabel="Register student"
          mutation={register}
          onSubmit={() =>
            register.mutate(
              {
                student_id: values.student_id,
                program_id: values.program_id,
                entry_session_id: values.entry_session_id,
                full_name: values.full_name,
                email: values.email || null,
                phone_number: values.phone_number || null,
                applicant_id: values.applicant_id || null,
              },
              { onSuccess: () => reset() }
            )
          }
          successTitle="Student registered"
          renderSuccess={(student) => (
            <span>
              Matric number <span className="font-mono">{student.matric_number}</span> issued.
            </span>
          )}
          footNote="The matric number is issued, not supplied — it encodes the department code and the entry year."
        >
          <FieldRow>
            <Input label="Student id" required placeholder="stu-0001" {...bind('student_id')} />
            <Input label="Full name" required {...bind('full_name')} />
          </FieldRow>
          <FieldRow>
            <Select label="Programme" required {...bind('program_id')}>
              <option value="">Select…</option>
              {(programs.data?.programs ?? []).map((program) => (
                <option key={program.program_id} value={program.program_id}>
                  {program.name}
                </option>
              ))}
            </Select>
            <Input
              label="Entry session"
              required
              placeholder="sess-2026-2027"
              {...bind('entry_session_id')}
            />
          </FieldRow>
          <FieldRow>
            <Input label="Email" type="email" {...bind('email')} />
            <Input label="Phone" {...bind('phone_number')} />
          </FieldRow>
          <Input
            label="Applicant id"
            {...bind('applicant_id')}
            hint="Optional. Links this student to the application they came from."
          />
          <ErrorNote error={programs.error} title="Could not load programmes" />
        </FormCard>
      </div>
    </>
  )
}
