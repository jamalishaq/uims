import { useState } from 'react'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Button from '../../components/ui/Button'
import PageHeader from '../../components/PageHeader'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import {
  useAlternativePolicy,
  usePublishAlternativePolicy,
} from '../../features/admissions/queries'
import useTitle from '../../hooks/useTitle'

/**
 * Alternative-programme chains: where a full programme overflows to.
 *
 * **This is the faculty's to publish and not a department's**, and the reason is worth keeping
 * in front of whoever is doing it: a chain spends *other departments'* quota. One department
 * pointing at another's places unilaterally is the thing this arrangement exists to prevent.
 *
 * **Order is the policy.** The offer flow walks the chain in order and gives the applicant the
 * first qualifying programme with a place left, so this is a list and not a set. Dragging is
 * unnecessary — the field is ordered text and the preview numbers it.
 *
 * **A chain is published once per session and cannot be republished.** A second write for the
 * same `(programme, session)` is a 409, because republishing would judge one cohort by two
 * standards. Next session is a different key.
 */
export default function OfferChains() {
  useTitle('Offer chains')
  const publish = usePublishAlternativePolicy()

  const { values, bind } = useFields({
    program_id: '',
    session_id: '',
    alternatives: '',
  })

  const [lookup, setLookup] = useState({ programId: '', sessionId: '' })
  const [viewing, setViewing] = useState(null)
  const policy = useAlternativePolicy(viewing?.programId, viewing?.sessionId)

  const alternatives = values.alternatives
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)

  return (
    <>
      <PageHeader
        title="Offer chains"
        description="Where an applicant goes when the programme they applied to is full."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <FormCard
            title="Publish a chain"
            description="For one programme, in one session."
            submitLabel="Publish chain"
            variant="caution"
            mutation={publish}
            onSubmit={() =>
              publish.mutate({
                program_id: values.program_id,
                session_id: values.session_id,
                alternatives,
              })
            }
            successTitle="Chain published"
            renderSuccess={(published) => (
              <span>
                {published.alternatives.length} alternative
                {published.alternatives.length === 1 ? '' : 's'} for{' '}
                <span className="font-mono">{published.program_id}</span>.
              </span>
            )}
            footNote="Published once per session. A second publish for the same programme and session is refused."
          >
            <FieldRow>
              <Input
                label="Programme"
                required
                placeholder="prog-csc"
                {...bind('program_id')}
                hint="The programme that overflows."
              />
              <Input
                label="Session"
                required
                placeholder="sess-2026-2027"
                {...bind('session_id')}
              />
            </FieldRow>
            <Input
              label="Alternatives, best first"
              placeholder="prog-mth, prog-phy"
              {...bind('alternatives')}
              hint="Comma separated. The order is the preference order."
            />

            {alternatives.length > 0 && (
              <div className="rounded-lg border border-ink-200 px-4 py-3 dark:border-ink-800">
                <p className="mb-2 hint">The offer flow will try, in this order:</p>
                <ol className="space-y-1 text-sm">
                  <li className="text-ink-900 dark:text-ink-100">
                    <span className="mr-2 font-mono text-ink-400">0.</span>
                    <span className="font-mono">{values.program_id || 'the applied programme'}</span>{' '}
                    <span className="hint">— what they applied to</span>
                  </li>
                  {alternatives.map((alternative, index) => (
                    <li key={alternative} className="text-ink-900 dark:text-ink-100">
                      <span className="mr-2 font-mono text-ink-400">{index + 1}.</span>
                      <span className="font-mono">{alternative}</span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </FormCard>

          <Note tone="info" title="A missing alternative is skipped, not an error">
            If an alternative has no open cycle or no published requirement this session, the
            flow steps over it and tries the next. A chain written before a session opened will
            name programmes that are not running, and refusing would deny a place the next
            alternative had free.
          </Note>
        </div>

        <Card>
          <CardHeader title="Read a published chain" />
          <CardBody>
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault()
                setViewing({ ...lookup })
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
              <Button type="submit">Read chain</Button>
            </form>

            {viewing && (
              <div className="mt-5 border-t border-ink-200 pt-4 dark:border-ink-800">
                {policy.isLoading ? (
                  <Loading />
                ) : policy.error ? (
                  <EmptyState
                    title="No chain published"
                    description="Nobody has published one for this programme and session. Applicants who cannot be placed will simply get no offer."
                  />
                ) : policy.data.alternatives.length === 0 ? (
                  <Note tone="warning" title="A chain was published, and it is empty">
                    That is different from no chain at all: somebody decided this programme
                    overflows nowhere.
                  </Note>
                ) : (
                  <ol className="space-y-2">
                    {policy.data.alternatives.map((alternative, index) => (
                      <li
                        key={alternative}
                        className="flex items-center gap-3 rounded-lg bg-ink-50 px-3 py-2 text-sm dark:bg-ink-800/60"
                      >
                        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-brand-600 text-xs font-medium text-white">
                          {index + 1}
                        </span>
                        <span className="font-mono">{alternative}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            )}
            <ErrorNote error={publish.error} className="mt-4" />
          </CardBody>
        </Card>
      </div>
    </>
  )
}
