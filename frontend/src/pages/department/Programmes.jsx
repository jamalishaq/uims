import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Button from '../../components/ui/Button'
import PageHeader from '../../components/PageHeader'
import Badge from '../../components/ui/Badge'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import {
  useCreateProgram,
  useDepartmentPrograms,
  useSetProgramAdmissions,
} from '../../features/facultyDepartment/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * The department's programmes, and the one switch that opens them to applications.
 *
 * **A programme is created *not* admitting.** Setting the flag is a separate act, so a
 * programme cannot start taking applications as a side effect of being described. The two are
 * separate panels here for the same reason they are separate use cases.
 */
export default function Programmes() {
  useTitle('Programmes')
  const { scopeId } = useAuth()
  const programs = useDepartmentPrograms(scopeId)
  const create = useCreateProgram()
  const setAdmissions = useSetProgramAdmissions()

  const { values, bind, reset } = useFields({ program_id: '', name: '', code: '' })

  const submit = () =>
    create.mutate(
      { ...values, department_id: scopeId },
      { onSuccess: () => reset() }
    )

  return (
    <>
      <PageHeader
        title="Programmes"
        description="What this department offers, and whether each is taking applications."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader
            title="Current programmes"
            description={`In ${scopeId}`}
          />
          {programs.isLoading ? (
            <Loading />
          ) : programs.error ? (
            <CardBody>
              <ErrorNote error={programs.error} />
            </CardBody>
          ) : programs.data.programs.length === 0 ? (
            <EmptyState
              title="No programmes yet"
              description="Create one alongside. It will start closed to applications."
            />
          ) : (
            <CardBody className="space-y-3">
              {programs.data.programs.map((program) => (
                <div
                  key={program.program_id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-ink-200 px-4 py-3 dark:border-ink-800"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink-900 dark:text-ink-100">
                      {program.name}
                    </p>
                    <p className="font-mono hint">
                      {program.program_id} · {program.code}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={program.is_admitting ? 'success' : 'neutral'}>
                      {program.is_admitting ? 'Admitting' : 'Closed'}
                    </Badge>
                    <Button
                      size="sm"
                      variant={program.is_admitting ? 'secondary' : 'primary'}
                      loading={
                        setAdmissions.isPending &&
                        setAdmissions.variables?.programId === program.program_id
                      }
                      onClick={() =>
                        setAdmissions.mutate({
                          programId: program.program_id,
                          isAdmitting: !program.is_admitting,
                        })
                      }
                    >
                      {program.is_admitting ? 'Close' : 'Open'}
                    </Button>
                  </div>
                </div>
              ))}
              <ErrorNote error={setAdmissions.error} title="Could not change that" />
            </CardBody>
          )}
        </Card>

        <div className="space-y-6">
          <FormCard
            title="Create a programme"
            description="It will be closed to applications until you open it."
            submitLabel="Create programme"
            mutation={create}
            onSubmit={submit}
            successTitle="Programme created"
            renderSuccess={(program) => (
              <span>
                <span className="font-mono">{program.program_id}</span> — closed to applications.
              </span>
            )}
            footNote={`Created in ${scopeId}. You may only create in your own department.`}
          >
            <Input
              label="Programme id"
              required
              placeholder="prog-csc"
              {...bind('program_id')}
            />
            <FieldRow>
              <Input
                label="Name"
                required
                placeholder="B.Sc. Computer Science"
                {...bind('name')}
              />
              <Input label="Code" required placeholder="CSC-BSC" {...bind('code')} />
            </FieldRow>
          </FormCard>

          <Note tone="info" title="Opening admissions is not the whole story">
            A programme that is admitting still needs an <strong>admission cycle</strong> (its
            quota) and a published <strong>entry requirement</strong> before anyone can be
            screened or offered a place. Both live under Admissions.
          </Note>
        </div>
      </div>
    </>
  )
}
