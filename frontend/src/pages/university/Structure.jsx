import { useState } from 'react'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Button from '../../components/ui/Button'
import PageHeader, { Detail } from '../../components/PageHeader'
import Badge from '../../components/ui/Badge'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import {
  useCreateDepartment,
  useCreateFaculty,
  useCreateProgram,
  useDepartmentPrograms,
  useProgramPlacement,
} from '../../features/facultyDepartment/queries'
import useTitle from '../../hooks/useTitle'

/**
 * The academic structure, top to bottom.
 *
 * A university principal may create at every level, which is why all three forms are here — a
 * faculty officer only gets departments and a registrar only gets programmes.
 *
 * **Each creation checks the level above it.** A department's faculty and a programme's
 * department must exist, and a 404 means the parent does not. That check is why a typo cannot
 * become a department hanging off nothing, which would otherwise surface far away and much
 * later as a programme placement that cannot be read.
 */
export default function Structure() {
  useTitle('Structure')

  const faculty = useCreateFaculty()
  const department = useCreateDepartment()
  const program = useCreateProgram()

  const facultyFields = useFields({ faculty_id: '', name: '', code: '' })
  const departmentFields = useFields({ department_id: '', faculty_id: '', name: '', code: '' })
  const programFields = useFields({ program_id: '', department_id: '', name: '', code: '' })

  const [lookup, setLookup] = useState({ programId: '', sessionId: '' })
  const [placementOf, setPlacementOf] = useState(null)
  const placement = useProgramPlacement(placementOf?.programId, placementOf?.sessionId)

  const [departmentId, setDepartmentId] = useState('')
  const [browsing, setBrowsing] = useState('')
  const programs = useDepartmentPrograms(browsing)

  return (
    <>
      <PageHeader
        title="Academic structure"
        description="Faculties, the departments inside them, and the programmes those offer."
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <FormCard
          title="Faculty"
          description="The top of the tree."
          submitLabel="Create faculty"
          mutation={faculty}
          onSubmit={() => faculty.mutate(facultyFields.values, { onSuccess: facultyFields.reset })}
          successTitle="Faculty created"
        >
          <Input label="Faculty id" required placeholder="fac-sci" {...facultyFields.bind('faculty_id')} />
          <Input label="Name" required placeholder="Faculty of Science" {...facultyFields.bind('name')} />
          <Input label="Code" required placeholder="SCI" {...facultyFields.bind('code')} />
        </FormCard>

        <FormCard
          title="Department"
          description="Must name a faculty that exists."
          submitLabel="Create department"
          mutation={department}
          onSubmit={() =>
            department.mutate(departmentFields.values, { onSuccess: departmentFields.reset })
          }
          successTitle="Department created"
        >
          <Input
            label="Department id"
            required
            placeholder="dept-csc"
            {...departmentFields.bind('department_id')}
          />
          <Input
            label="Faculty id"
            required
            placeholder="fac-sci"
            {...departmentFields.bind('faculty_id')}
            hint="A 404 means no such faculty."
          />
          <FieldRow>
            <Input label="Name" required {...departmentFields.bind('name')} />
            <Input label="Code" required placeholder="CSC" {...departmentFields.bind('code')} />
          </FieldRow>
        </FormCard>

        <FormCard
          title="Programme"
          description="Created closed to applications."
          submitLabel="Create programme"
          mutation={program}
          onSubmit={() => program.mutate(programFields.values, { onSuccess: programFields.reset })}
          successTitle="Programme created"
          renderSuccess={() => <span>Closed to applications until somebody opens it.</span>}
        >
          <Input
            label="Programme id"
            required
            placeholder="prog-csc"
            {...programFields.bind('program_id')}
          />
          <Input
            label="Department id"
            required
            placeholder="dept-csc"
            {...programFields.bind('department_id')}
          />
          <FieldRow>
            <Input label="Name" required {...programFields.bind('name')} />
            <Input label="Code" required {...programFields.bind('code')} />
          </FieldRow>
        </FormCard>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="A department's programmes"
            description="The only way to walk down the tree — nothing lists faculties or departments."
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
                {programs.isLoading ? (
                  <Loading />
                ) : programs.data?.programs.length === 0 ? (
                  <EmptyState
                    title="Nothing here"
                    description="No programmes — or no such department. The read answers the same either way."
                  />
                ) : (
                  <ul className="space-y-2">
                    {(programs.data?.programs ?? []).map((p) => (
                      <li
                        key={p.program_id}
                        className="flex items-center justify-between gap-3 border-b border-ink-100 py-2 text-sm last:border-0 dark:border-ink-800"
                      >
                        <span className="font-mono">{p.program_id}</span>
                        <Badge tone={p.is_admitting ? 'success' : 'neutral'}>
                          {p.is_admitting ? 'Admitting' : 'Closed'}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Programme placement"
            description="Where a programme sits, and whether it is taking anybody, for one session."
          />
          <CardBody>
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault()
                setPlacementOf({ ...lookup })
              }}
            >
              <FieldRow>
                <Input
                  label="Programme"
                  required
                  value={lookup.programId}
                  onChange={(e) => setLookup((l) => ({ ...l, programId: e.target.value }))}
                />
                <Input
                  label="Session"
                  required
                  value={lookup.sessionId}
                  onChange={(e) => setLookup((l) => ({ ...l, sessionId: e.target.value }))}
                />
              </FieldRow>
              <Button type="submit">Read placement</Button>
            </form>

            {placementOf && (
              <div className="mt-5 border-t border-ink-200 pt-4 dark:border-ink-800">
                {placement.isLoading ? (
                  <Loading />
                ) : placement.error ? (
                  <EmptyState
                    title="No placement"
                    description="Either the programme does not exist, or that session does not."
                  />
                ) : (
                  <dl>
                    <Detail label="Programme" value={placement.data.program_id} mono />
                    <Detail label="Department" value={placement.data.department_id} mono />
                    <Detail label="Department code" value={placement.data.department_code} mono />
                    <Detail label="Faculty" value={placement.data.faculty_id} mono />
                    <Detail
                      label="Admitting"
                      value={
                        <Badge tone={placement.data.is_admitting ? 'success' : 'neutral'}>
                          {placement.data.is_admitting ? 'Yes' : 'No'}
                        </Badge>
                      }
                    />
                    <Detail
                      label="Session open"
                      value={
                        <Badge tone={placement.data.session_is_open ? 'success' : 'warning'}>
                          {placement.data.session_is_open ? 'Open' : 'Not open'}
                        </Badge>
                      }
                    />
                  </dl>
                )}
              </div>
            )}
            <ErrorNote error={programs.error} className="mt-4" />
          </CardBody>
        </Card>
      </div>

      <Note tone="info" className="mt-6" title="The department code here is not the matric code">
        This is the alphabetic code the structure holds — <span className="font-mono">CSC</span>.
        The four digits a matric number carries are a separate register, configured on the
        server, and deliberately do not appear here.
      </Note>
    </>
  )
}
