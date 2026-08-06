import { useState } from 'react'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Button from '../../components/ui/Button'
import PageHeader from '../../components/PageHeader'
import Badge from '../../components/ui/Badge'
import { ErrorNote, Note } from '../../components/ui/Feedback'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import { useOpenSession, usePlanSession } from '../../features/facultyDepartment/queries'
import useTitle from '../../hooks/useTitle'

/**
 * Planning a session, and opening one.
 *
 * **These are two acts and the page keeps them apart deliberately.** A session is described
 * months before it starts, and describing it must not charge anybody. Opening it is the only
 * publisher of `SessionOpened` in the whole system, and Billing reacts by batch-applying the
 * session's fee schedule to **every active account** — so "open" is not a status flip, it bills
 * a cohort.
 *
 * That is why the open control is a two-step confirmation in the `caution` variant rather than
 * a toggle. A toggle that invoiced a thousand students would be the worst affordance in the app.
 */
export default function Sessions() {
  useTitle('Sessions')
  const plan = usePlanSession()
  const open = useOpenSession()

  const { values, bind, reset } = useFields({
    session_id: '',
    academic_year: '',
    first_semester_id: '',
    second_semester_id: '',
  })

  const [openingId, setOpeningId] = useState('')
  const [confirming, setConfirming] = useState(false)

  return (
    <>
      <PageHeader
        title="Academic sessions"
        description="Describe a session first. Opening it is a separate, billing act."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <FormCard
          title="Plan a session"
          description="Describes it. Charges nobody."
          submitLabel="Plan session"
          mutation={plan}
          onSubmit={() =>
            plan.mutate(
              {
                session_id: values.session_id,
                academic_year: Number(values.academic_year),
                semesters: [
                  { semester_id: values.first_semester_id, ordinal: 1 },
                  { semester_id: values.second_semester_id, ordinal: 2 },
                ],
              },
              { onSuccess: reset }
            )
          }
          successTitle="Session planned"
          renderSuccess={(session) => (
            <span>
              {session.label} — <Badge tone="neutral">{session.status}</Badge> Nobody has been
              billed.
            </span>
          )}
        >
          <FieldRow>
            <Input
              label="Session id"
              required
              placeholder="sess-2026-2027"
              {...bind('session_id')}
            />
            <Input
              label="Academic year"
              type="number"
              required
              placeholder="2026"
              {...bind('academic_year')}
              hint="The starting year. The label is derived from it."
            />
          </FieldRow>
          <FieldRow>
            <Input
              label="First semester id"
              required
              placeholder="sem-2026-1"
              {...bind('first_semester_id')}
            />
            <Input
              label="Second semester id"
              required
              placeholder="sem-2026-2"
              {...bind('second_semester_id')}
            />
          </FieldRow>
        </FormCard>

        <Card>
          <CardHeader
            title="Open a session"
            description="This bills every active account."
          />
          <CardBody className="space-y-4">
            <Note tone="warning" title="Opening a session is not a status change">
              Billing applies the session&rsquo;s fee schedule to every active student account
              the moment this runs. A combination the schedule does not price is skipped and
              reported; a session with no schedule at all is refused outright.
            </Note>

            <Input
              label="Session id"
              placeholder="sess-2026-2027"
              value={openingId}
              onChange={(e) => {
                setOpeningId(e.target.value)
                setConfirming(false)
              }}
            />

            {!confirming ? (
              <Button
                variant="caution"
                disabled={!openingId.trim()}
                onClick={() => setConfirming(true)}
              >
                Open session…
              </Button>
            ) : (
              <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/50">
                <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
                  Open <span className="font-mono">{openingId}</span> and bill the cohort?
                </p>
                <p className="mt-1 text-sm text-amber-800/80 dark:text-amber-300/80">
                  This cannot be undone from here. Re-running it is safe — a charge is raised
                  once per kind and session — but the invoices go out now.
                </p>
                <div className="mt-3 flex gap-2">
                  <Button
                    variant="caution"
                    size="sm"
                    loading={open.isPending}
                    onClick={() =>
                      open.mutate(openingId.trim(), {
                        onSuccess: () => setConfirming(false),
                      })
                    }
                  >
                    Yes, open and bill
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            )}

            <ErrorNote error={open.error} title="Session not opened" />

            {open.data && (
              <Note tone="success" title={`${open.data.label} is open`}>
                Status <Badge tone="success">{open.data.status}</Badge> — the fee schedule has
                been applied. Check the bursary page for anything the schedule could not price.
              </Note>
            )}
          </CardBody>
        </Card>
      </div>

      <Note tone="info" className="mt-6" title="Why re-opening is safe but re-billing is not">
        A charge is raised once per <em>(kind, session)</em>, so a redelivered event or a second
        open does not double-bill. What it will not do is un-bill: there is no route that
        reverses a charge, and refunds are a deferred admin use case.
      </Note>
    </>
  )
}
