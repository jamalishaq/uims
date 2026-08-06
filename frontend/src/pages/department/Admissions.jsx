import { useState } from 'react'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import Button from '../../components/ui/Button'
import PageHeader, { StatTile } from '../../components/PageHeader'
import Badge, { StatusBadge } from '../../components/ui/Badge'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import { useDepartmentPrograms } from '../../features/facultyDepartment/queries'
import {
  useAcceptOffer,
  useAdmissionsSummary,
  useDeclineOffer,
  useEntryRequirement,
  useMakeOffer,
  useMatriculateApplicant,
  useOpenAdmissionCycle,
  useProgramApplicants,
  usePublishEntryRequirement,
  useScreenApplicant,
} from '../../features/admissions/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

const STATUSES = [
  'applied',
  'screened',
  'offered',
  'accepted',
  'declined',
  'matriculated',
  // The enum's wire value, spaces and all. An unrecognised filter is a 422 rather than an
  // empty list, deliberately — a typo that read as "no applicants" is one a registrar acts on.
  'no offer available',
]

/**
 * The registrar's working surface: policy, the funnel, and the list.
 *
 * **Everything is keyed by `(programme, session)`**, because that is how Admissions holds every
 * fact about a programme. The programme picker is fed from Faculty & Department — an applicant
 * carries programmes and never a department, so a department's list has to come from over
 * there and then be asked about here, one programme at a time.
 *
 * **The two figures do not add up, and the page says so.** Places claimed counts anyone who
 * landed *on* this programme, including overflow from another programme's fallback chain. The
 * funnel counts everyone who applied *to* it, including those placed elsewhere. Presenting
 * either as the other is how a department discovers in September that it admitted people it
 * never saw.
 */
export default function Admissions() {
  useTitle('Admissions')
  const { scopeId } = useAuth()
  const programs = useDepartmentPrograms(scopeId)

  const [programId, setProgramId] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const chosen = Boolean(programId && sessionId)
  const summary = useAdmissionsSummary(programId, sessionId)
  const requirement = useEntryRequirement(programId, sessionId)
  const applicants = useProgramApplicants(programId, sessionId, statusFilter || undefined)

  const openCycle = useOpenAdmissionCycle()
  const publishRequirement = usePublishEntryRequirement()

  const cycleFields = useFields({ quota: '' })
  const requirementFields = useFields({ required_subjects: '', one_of_groups: '' })

  return (
    <>
      <PageHeader
        title="Admissions"
        description="Quotas, entry requirements, and the applicants for one programme in one session."
      />

      <Card className="mb-6">
        <CardBody>
          <FieldRow columns={3}>
            <Select
              label="Programme"
              value={programId}
              onChange={(e) => setProgramId(e.target.value)}
              hint="Your department's programmes."
            >
              <option value="">Select a programme…</option>
              {(programs.data?.programs ?? []).map((program) => (
                <option key={program.program_id} value={program.program_id}>
                  {program.name} ({program.program_id})
                </option>
              ))}
            </Select>
            <Input
              label="Session"
              placeholder="sess-2026-2027"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              hint="Everything here is scoped to a session."
            />
            <Select
              label="Filter by status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              disabled={!chosen}
            >
              <option value="">All applicants</option>
              {STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </Select>
          </FieldRow>
        </CardBody>
      </Card>

      {!chosen ? (
        <EmptyState
          title="Choose a programme and a session"
          description="Admissions holds nothing about a programme in general — only about a programme in a session."
        />
      ) : (
        <>
          {summary.data && (
            <>
              <h2 className="mb-3 text-sm font-semibold text-ink-900 dark:text-ink-100">
                Capacity — places claimed on this programme
              </h2>
              <div className="mb-6 grid gap-4 sm:grid-cols-4">
                <StatTile
                  label="Quota"
                  value={summary.data.quota ?? '—'}
                  caption={summary.data.quota === null ? 'No cycle opened' : undefined}
                />
                <StatTile label="Places claimed" value={summary.data.offers_made ?? '—'} />
                <StatTile
                  label="Places left"
                  value={summary.data.places_remaining ?? '—'}
                  tone={summary.data.is_full ? 'danger' : 'success'}
                />
                <StatTile
                  label="Status"
                  value={
                    summary.data.quota === null ? (
                      <Badge tone="warning">Not opened</Badge>
                    ) : summary.data.is_full ? (
                      <Badge tone="danger">Full</Badge>
                    ) : (
                      <Badge tone="success">Open</Badge>
                    )
                  }
                />
              </div>

              <h2 className="mb-3 text-sm font-semibold text-ink-900 dark:text-ink-100">
                Cohort — applicants who applied to this programme
              </h2>
              <div className="mb-4 grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
                {[
                  ['Applied', summary.data.applied],
                  ['Screened', summary.data.screened],
                  ['Offered', summary.data.offered],
                  ['Accepted', summary.data.accepted],
                  ['Declined', summary.data.declined],
                  ['Matriculated', summary.data.matriculated],
                ].map(([label, value]) => (
                  <StatTile key={label} label={label} value={value} />
                ))}
              </div>

              <Note tone="info" className="mb-6">
                These two blocks count different populations and will not reconcile. Places
                claimed includes applicants who applied elsewhere and overflowed in through
                another programme&rsquo;s fallback chain; the cohort includes applicants placed
                somewhere else. Both are true.
              </Note>
            </>
          )}

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
            <ApplicantList
              query={applicants}
              summaryFull={summary.data?.is_full}
            />

            <div className="space-y-6">
              <FormCard
                title="Open the intake"
                description="Sets the quota. This cannot be re-run."
                submitLabel="Open cycle"
                variant="caution"
                mutation={openCycle}
                onSubmit={() =>
                  openCycle.mutate({
                    program_id: programId,
                    session_id: sessionId,
                    quota: Number(cycleFields.values.quota),
                  })
                }
                successTitle="Intake opened"
                footNote="Opening a second time is refused: it would reset the count of places held and re-sell them."
              >
                <Input
                  label="Quota"
                  type="number"
                  min={1}
                  required
                  {...cycleFields.bind('quota')}
                  hint="There is no resize. Choose carefully."
                />
              </FormCard>

              <FormCard
                title="Publish the entry requirement"
                description="What screening judges against."
                submitLabel="Publish"
                variant="caution"
                mutation={publishRequirement}
                onSubmit={() =>
                  publishRequirement.mutate({
                    program_id: programId,
                    session_id: sessionId,
                    required_subjects: splitList(requirementFields.values.required_subjects),
                    one_of_groups: requirementFields.values.one_of_groups
                      .split('\n')
                      .map(splitList)
                      .filter((group) => group.length > 0),
                  })
                }
                successTitle="Requirement published"
                footNote="Published once per session. Republishing would judge one cohort by two standards."
              >
                <Input
                  label="Required subjects"
                  placeholder="USE OF ENGLISH, MATHEMATICS"
                  {...requirementFields.bind('required_subjects')}
                  hint="Comma separated. Every applicant must have all of these."
                />
                <div>
                  <label className="label" htmlFor="one-of-groups">
                    One-of groups
                  </label>
                  <textarea
                    id="one-of-groups"
                    rows={3}
                    className="mt-1.5 w-full rounded-lg border border-ink-300 bg-white px-3 py-2 text-sm dark:border-ink-700 dark:bg-ink-800"
                    placeholder={'PHYSICS, CHEMISTRY\nBIOLOGY, AGRICULTURE'}
                    {...requirementFields.bind('one_of_groups')}
                  />
                  <p className="mt-1.5 hint">
                    One group per line, comma separated within a line. The applicant must have at
                    least one subject from each group.
                  </p>
                </div>
              </FormCard>

              {requirement.data && (
                <Card>
                  <CardHeader title="Published requirement" />
                  <CardBody className="space-y-3 text-sm">
                    <div>
                      <p className="hint">Required</p>
                      <p className="text-ink-900 dark:text-ink-100">
                        {requirement.data.required_subjects.join(', ') || '—'}
                      </p>
                    </div>
                    <div>
                      <p className="hint">One of each group</p>
                      {requirement.data.one_of_groups.length === 0 ? (
                        <p className="text-ink-900 dark:text-ink-100">—</p>
                      ) : (
                        <ul className="list-inside list-disc text-ink-900 dark:text-ink-100">
                          {requirement.data.one_of_groups.map((group, index) => (
                            <li key={index}>{group.join(' / ')}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </CardBody>
                </Card>
              )}
            </div>
          </div>
        </>
      )}
    </>
  )
}

const splitList = (raw) =>
  raw
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)

/**
 * The working list, and the acts a registrar performs on one applicant at a time.
 *
 * Screening and offering both answer **200 with an outcome**, never a 4xx — "not qualified" and
 * "no offer available" are decisions, not errors. The buttons show what came back rather than
 * treating either as a failure.
 */
function ApplicantList({ query, summaryFull }) {
  const screen = useScreenApplicant()
  const offer = useMakeOffer()
  const accept = useAcceptOffer()
  const decline = useDeclineOffer()
  const matriculate = useMatriculateApplicant()

  const busy = [screen, offer, accept, decline, matriculate].find((m) => m.isPending)
  const failure = [screen, offer, accept, decline, matriculate].find((m) => m.error)

  return (
    <Card>
      <CardHeader
        title="Applicants"
        description="Keyed on the programme they applied to, so the offer flow cannot lose anybody."
      />
      {query.isLoading ? (
        <Loading />
      ) : query.error ? (
        <CardBody>
          <ErrorNote error={query.error} />
        </CardBody>
      ) : query.data.applicants.length === 0 ? (
        <EmptyState
          title="Nobody has applied"
          description="An empty list means no applications, not a filter problem."
        />
      ) : (
        <CardBody className="space-y-3">
          {failure && <ErrorNote error={failure.error} />}
          {summaryFull && (
            <Note tone="warning">
              This programme is full. Further offers will fall through to the alternative chain,
              if the faculty has published one.
            </Note>
          )}
          {query.data.applicants.map((applicant) => (
            <div
              key={applicant.applicant_id}
              className="rounded-lg border border-ink-200 px-4 py-3 dark:border-ink-800"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink-900 dark:text-ink-100">
                    {applicant.full_name}
                  </p>
                  <p className="font-mono hint">{applicant.applicant_id}</p>
                  {applicant.offered_program_id &&
                    applicant.offered_program_id !== applicant.applied_program_id && (
                      <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                        Offered {applicant.offered_program_id} instead
                      </p>
                    )}
                </div>
                <div className="flex flex-col items-end gap-1.5">
                  <StatusBadge status={applicant.status} />
                  {applicant.is_fee_cleared && <Badge tone="success">Fee cleared</Badge>}
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                {applicant.status === 'applied' && (
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={Boolean(busy)}
                    onClick={() => screen.mutate(applicant.applicant_id)}
                  >
                    Screen
                  </Button>
                )}
                {applicant.status === 'screened' && (
                  <Button
                    size="sm"
                    disabled={Boolean(busy)}
                    onClick={() => offer.mutate(applicant.applicant_id)}
                  >
                    Decide an offer
                  </Button>
                )}
                {applicant.status === 'offered' && (
                  <>
                    <Button
                      size="sm"
                      disabled={Boolean(busy)}
                      onClick={() => accept.mutate(applicant.applicant_id)}
                    >
                      Record acceptance
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      disabled={Boolean(busy)}
                      onClick={() => decline.mutate(applicant.applicant_id)}
                    >
                      Record decline
                    </Button>
                  </>
                )}
                {applicant.status === 'accepted' && (
                  <Button
                    size="sm"
                    variant="caution"
                    disabled={Boolean(busy) || !applicant.is_fee_cleared}
                    title={
                      applicant.is_fee_cleared
                        ? undefined
                        : 'The acceptance fee has not cleared yet.'
                    }
                    onClick={() => matriculate.mutate(applicant.applicant_id)}
                  >
                    Matriculate
                  </Button>
                )}
                {applicant.is_final && (
                  <span className="self-center text-xs text-ink-500">
                    No further action possible.
                  </span>
                )}
              </div>
            </div>
          ))}
        </CardBody>
      )}
    </Card>
  )
}
