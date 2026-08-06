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
  useCreateDepartment,
  useDepartmentPrograms,
} from '../../features/facultyDepartment/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * Create a department, and look into one you already know the id of.
 *
 * The inspect panel takes an id rather than offering a picker for the reason the overview gives:
 * no route lists a faculty's departments. What it *can* do is read that department's programmes,
 * which is a real route and the useful thing to see.
 */
export default function Departments() {
  useTitle('Departments')
  const { scopeId } = useAuth()
  const create = useCreateDepartment()

  const { values, bind, reset } = useFields({ department_id: '', name: '', code: '' })
  const [inspecting, setInspecting] = useState('')
  const [inspected, setInspected] = useState('')
  const programs = useDepartmentPrograms(inspected)

  return (
    <>
      <PageHeader
        title="Departments"
        description={
          <>
            Inside <span className="font-mono">{scopeId}</span>.
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <FormCard
          title="Create a department"
          description="It will sit inside your faculty."
          submitLabel="Create department"
          mutation={create}
          onSubmit={() =>
            create.mutate(
              { ...values, faculty_id: scopeId },
              { onSuccess: () => reset() }
            )
          }
          successTitle="Department created"
          renderSuccess={(department) => (
            <span>
              <span className="font-mono">{department.department_id}</span> in{' '}
              <span className="font-mono">{department.faculty_id}</span>.
            </span>
          )}
          footNote={`Created inside ${scopeId}. The server refuses any other faculty.`}
        >
          <Input
            label="Department id"
            required
            placeholder="dept-csc"
            {...bind('department_id')}
          />
          <FieldRow>
            <Input label="Name" required placeholder="Computer Science" {...bind('name')} />
            <Input
              label="Code"
              required
              placeholder="CSC"
              {...bind('code')}
              hint="The alphabetic code. The numeric one in matric numbers is separate."
            />
          </FieldRow>
        </FormCard>

        <Card>
          <CardHeader
            title="Inspect a department"
            description="See what a department offers."
          />
          <CardBody>
            <form
              className="flex items-end gap-3"
              onSubmit={(event) => {
                event.preventDefault()
                setInspected(inspecting.trim())
              }}
            >
              <Input
                label="Department id"
                className="flex-1"
                required
                placeholder="dept-csc"
                value={inspecting}
                onChange={(e) => setInspecting(e.target.value)}
              />
              <Button type="submit">Look up</Button>
            </form>

            {inspected && (
              <div className="mt-5 border-t border-ink-200 pt-4 dark:border-ink-800">
                {programs.isLoading ? (
                  <Loading />
                ) : programs.error ? (
                  <ErrorNote error={programs.error} />
                ) : programs.data.programs.length === 0 ? (
                  <EmptyState
                    title="No programmes"
                    description="Either this department offers none, or there is no such department — the API answers an empty list for both."
                  />
                ) : (
                  <ul className="space-y-2">
                    {programs.data.programs.map((program) => (
                      <li
                        key={program.program_id}
                        className="flex items-center justify-between gap-3 border-b border-ink-100 py-2 text-sm last:border-0 dark:border-ink-800"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-ink-900 dark:text-ink-100">{program.name}</p>
                          <p className="font-mono hint">{program.program_id}</p>
                        </div>
                        <Badge tone={program.is_admitting ? 'success' : 'neutral'}>
                          {program.is_admitting ? 'Admitting' : 'Closed'}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      <Note tone="warning" className="mt-6" title="An empty list is ambiguous here">
        A department nobody has and a department with no programmes both come back empty — the
        read raises nothing for an unknown id. If you expected programmes, check the id first.
      </Note>
    </>
  )
}
