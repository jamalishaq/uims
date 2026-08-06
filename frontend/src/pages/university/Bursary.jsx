import { useState } from 'react'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import Button from '../../components/ui/Button'
import PageHeader, { Detail, StatTile } from '../../components/PageHeader'
import Badge, { humanise } from '../../components/ui/Badge'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import {
  useAccount,
  useApplySessionFees,
  useLinkStudentAccount,
  useRecordPayment,
  useReconcile,
} from '../../features/billing/queries'
import useTitle from '../../hooks/useTitle'

/**
 * The bursary's four acts: read a ledger, record a payment, apply session fees, reconcile.
 *
 * **Amounts are the server's strings throughout.** Nothing on this page adds up money in
 * JavaScript — every total shown was computed by the ledger, which holds exact decimals. This
 * is the one screen where a floating-point rounding error would be a real financial error.
 */
export default function Bursary() {
  useTitle('Bursary')

  const [partyId, setPartyId] = useState('')
  const [lookingUp, setLookingUp] = useState('')
  const account = useAccount(lookingUp)

  const recordPayment = useRecordPayment()
  const linkAccount = useLinkStudentAccount()
  const applyFees = useApplySessionFees()
  const reconcile = useReconcile()

  const payment = useFields({ gateway_ref: '', amount: '' })
  const link = useFields({ student_id: '' })
  const fees = useFields({ session_id: '' })

  return (
    <>
      <PageHeader
        title="Bursary"
        description="Ledgers, payments, session fees and the reconciliation sweep."
      />

      <Card className="mb-6">
        <CardHeader
          title="Find a ledger"
          description="By applicant id before matriculation, or matric number after. Either resolves."
        />
        <CardBody>
          <form
            className="flex items-end gap-3"
            onSubmit={(event) => {
              event.preventDefault()
              setLookingUp(partyId.trim())
            }}
          >
            <Input
              label="Party id"
              className="flex-1"
              required
              placeholder="260591001 or app-0001"
              value={partyId}
              onChange={(e) => setPartyId(e.target.value)}
            />
            <Button type="submit">Open ledger</Button>
          </form>
        </CardBody>
      </Card>

      {lookingUp &&
        (account.isLoading ? (
          <Loading />
        ) : account.error ? (
          <EmptyState
            title="No ledger for that id"
            description="An account is opened when an offer is accepted. Nothing exists before that."
          />
        ) : (
          <>
            <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile label="Charged" value={`₦${account.data.total_charged}`} />
              <StatTile label="Paid" value={`₦${account.data.total_paid}`} />
              <StatTile
                label="Outstanding"
                value={`₦${account.data.outstanding}`}
                tone={account.data.outstanding === '0.00' ? 'success' : 'warning'}
              />
              <StatTile
                label="Credit balance"
                value={`₦${account.data.credit_balance}`}
                caption="Surplus is allowed."
              />
            </div>

            <div className="mb-6 grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
              <Card>
                <CardHeader title="Charges" />
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-500 dark:bg-ink-800/60 dark:text-ink-400">
                      <tr>
                        <th className="px-5 py-2.5 text-left font-medium">Charge</th>
                        <th className="px-5 py-2.5 text-right font-medium">Amount</th>
                        <th className="px-5 py-2.5 text-right font-medium">Allocated</th>
                        <th className="px-5 py-2.5 text-right font-medium">Outstanding</th>
                      </tr>
                    </thead>
                    <tbody>
                      {account.data.charges.map((charge) => (
                        <tr
                          key={`${charge.kind}-${charge.session_id}`}
                          className="border-t border-ink-200 dark:border-ink-800"
                        >
                          <td className="px-5 py-3">
                            {humanise(charge.kind)}
                            {charge.gates_matriculation && (
                              <Badge tone="brand" className="ml-2">
                                Gating
                              </Badge>
                            )}
                            <p className="font-mono hint">{charge.session_id}</p>
                          </td>
                          <td className="tabular px-5 py-3 text-right">₦{charge.amount}</td>
                          <td className="tabular px-5 py-3 text-right">₦{charge.allocated}</td>
                          <td className="tabular px-5 py-3 text-right">₦{charge.outstanding}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>

              <Card>
                <CardHeader title="Account" />
                <CardBody>
                  <dl>
                    <Detail label="Party id" value={account.data.party_id} mono />
                    <Detail
                      label="Matric number"
                      value={
                        account.data.student_id ?? (
                          <Badge tone="warning">Not linked</Badge>
                        )
                      }
                      mono
                    />
                    <Detail label="Programme" value={account.data.program_id} mono />
                    <Detail label="Level" value={account.data.level} />
                    <Detail
                      label="Acceptance fee"
                      value={
                        <Badge tone={account.data.acceptance_fee_settled ? 'success' : 'warning'}>
                          {account.data.acceptance_fee_settled ? 'Settled' : 'Outstanding'}
                        </Badge>
                      }
                    />
                  </dl>
                </CardBody>
              </Card>
            </div>

            <div className="mb-6 grid gap-6 lg:grid-cols-2">
              <FormCard
                title="Record a payment"
                description="Idempotent on the gateway reference."
                submitLabel="Record payment"
                mutation={recordPayment}
                onSubmit={() =>
                  recordPayment.mutate({
                    partyId: lookingUp,
                    gatewayRef: payment.values.gateway_ref,
                    amount: payment.values.amount,
                  })
                }
                successTitle="Ledger updated"
                renderSuccess={(outcome) =>
                  outcome.outcome === 'duplicate_ignored' ? (
                    <span>
                      That reference was already recorded, so nothing changed. This is a success,
                      not a failure — duplicate deliveries are normal.
                    </span>
                  ) : (
                    <span>
                      ₦{outcome.credited} credited across {outcome.allocations.length} charge
                      {outcome.allocations.length === 1 ? '' : 's'}.
                    </span>
                  )
                }
                footNote="The ledger decides which charge a payment settles: the gating charge first, then in the order raised."
              >
                <FieldRow>
                  <Input label="Gateway reference" required {...payment.bind('gateway_ref')} />
                  <Input label="Amount" required inputMode="decimal" {...payment.bind('amount')} />
                </FieldRow>
              </FormCard>

              <FormCard
                title="Link to a matric number"
                description="For a ledger still keyed by an applicant id."
                submitLabel="Link account"
                mutation={linkAccount}
                onSubmit={() =>
                  linkAccount.mutate({
                    partyId: lookingUp,
                    studentId: link.values.student_id,
                  })
                }
                successTitle="Account linked"
                footNote="Until this is done the student cannot see their own ledger — their token has never heard of an applicant id."
              >
                <Input
                  label="Matric number"
                  required
                  placeholder="260591001"
                  {...link.bind('student_id')}
                />
              </FormCard>
            </div>
          </>
        ))}

      <div className="grid gap-6 lg:grid-cols-2">
        <FormCard
          title="Apply session fees"
          description="Batch-applies the schedule to every active account."
          submitLabel="Apply fees"
          variant="caution"
          mutation={applyFees}
          onSubmit={() => applyFees.mutate({ sessionId: fees.values.session_id })}
          successTitle="Batch complete"
          renderSuccess={(result) => (
            <div className="space-y-1">
              <p>
                {result.considered} accounts considered · {result.charged.length} charged ·{' '}
                {result.already_charged.length} already charged
              </p>
              {result.unpriced.length > 0 && (
                <p className="font-medium text-amber-800 dark:text-amber-300">
                  {result.unpriced.length} skipped as unpriced — those students are{' '}
                  <strong>not financially cleared</strong> and cannot register until the schedule
                  prices them.
                </p>
              )}
            </div>
          )}
          footNote="This normally happens automatically when a session is opened. Running it again is safe."
        >
          <Input label="Session id" required placeholder="sess-2026-2027" {...fees.bind('session_id')} />
        </FormCard>

        <Card>
          <CardHeader
            title="Reconcile payment intents"
            description="Verifies expired intents with the gateway before writing any off."
          />
          <CardBody className="space-y-4">
            <Note tone="info" title="What this is for">
              &ldquo;Webhook lost but money taken&rdquo; is the stuck state this catches. An
              intent the gateway confirms is recorded even though the clock had written it off —
              an abandonment is a presumption, a confirmation is a fact.
            </Note>
            <Button variant="caution" loading={reconcile.isPending} onClick={() => reconcile.mutate({})}>
              Run the sweep
            </Button>
            <ErrorNote error={reconcile.error} />
            {reconcile.data && (
              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <StatTile label="Examined" value={reconcile.data.examined} />
                  <StatTile
                    label="Recovered"
                    value={reconcile.data.confirmed.length}
                    tone={reconcile.data.recovered_money ? 'success' : 'neutral'}
                    caption="Money that had arrived unnoticed"
                  />
                  <StatTile label="Abandoned" value={reconcile.data.abandoned.length} />
                  <StatTile
                    label="Unreachable"
                    value={reconcile.data.unreachable.length}
                    tone={reconcile.data.unreachable.length > 0 ? 'warning' : 'neutral'}
                    caption="Left open, not written off"
                  />
                </div>
                {reconcile.data.unreachable.length > 0 && (
                  <Note tone="warning" title="Some intents could not be checked">
                    The gateway could not be reached about these, so they were left open rather
                    than abandoned. Run the sweep again later.
                  </Note>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      </div>
    </>
  )
}
