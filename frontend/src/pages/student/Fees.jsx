import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Input from '../../components/ui/Input'
import PageHeader, { Detail, StatTile } from '../../components/PageHeader'
import Badge from '../../components/ui/Badge'
import { Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { FieldRow, FormCard, useFields } from '../../components/Form'
import { useAccount, useInitiatePayment } from '../../features/billing/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import { humanise } from '../../components/ui/Badge'

/**
 * The ledger: what is owed, what has been paid, and what each payment settled.
 *
 * **Amounts are rendered as the strings the API sent.** They are exact decimals quantized to
 * kobo, and every total on this page — outstanding, allocated, credit balance — was computed by
 * the server. Adding them up in JavaScript would reintroduce floating-point error into money,
 * which is the one place it is not survivable.
 *
 * **A credit balance is normal.** The ledger allows surplus from an overpayment, so
 * `balance ≤ charges` is not an invariant and the page does not imply it is.
 */
export default function Fees() {
  useTitle('Fees')
  const { loginId } = useAuth()
  const { data: account, isLoading, error } = useAccount(loginId)
  const initiate = useInitiatePayment()

  const { values, bind } = useFields({ reference: '', amount: '' })

  const pay = () =>
    initiate.mutate({
      partyId: loginId,
      reference: values.reference,
      amount: values.amount,
    })

  if (isLoading) return <Loading label="Loading your ledger…" />

  if (error || !account) {
    return (
      <>
        <PageHeader title="Fees" />
        <EmptyState
          title="No ledger yet"
          description="An account is opened when you accept an offer, and linked to your matric number at matriculation. If you have just been matriculated, the link may not have been made yet — the bursary can do it."
        />
      </>
    )
  }

  return (
    <>
      <PageHeader title="Fees" description="Your ledger, from the acceptance fee onwards." />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Charged" value={`₦${account.total_charged}`} />
        <StatTile label="Paid" value={`₦${account.total_paid}`} />
        <StatTile
          label="Outstanding"
          value={`₦${account.outstanding}`}
          tone={account.outstanding === '0.00' ? 'success' : 'warning'}
        />
        <StatTile
          label="Credit balance"
          value={`₦${account.credit_balance}`}
          caption="Surplus from an overpayment. Absorbed by the next charge raised."
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <Card>
            <CardHeader
              title="Charges"
              description="Raised once per kind and session. Payments settle the gating charge first."
            />
            {account.charges.length === 0 ? (
              <EmptyState title="No charges" description="Nothing has been billed to you yet." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-500 dark:bg-ink-800/60 dark:text-ink-400">
                    <tr>
                      <th className="px-5 py-2.5 text-left font-medium">Charge</th>
                      <th className="px-5 py-2.5 text-right font-medium">Amount</th>
                      <th className="px-5 py-2.5 text-right font-medium">Paid</th>
                      <th className="px-5 py-2.5 text-right font-medium">Outstanding</th>
                    </tr>
                  </thead>
                  <tbody>
                    {account.charges.map((charge) => (
                      <tr
                        key={`${charge.kind}-${charge.session_id}`}
                        className="border-t border-ink-200 dark:border-ink-800"
                      >
                        <td className="px-5 py-3">
                          <span className="text-ink-900 dark:text-ink-100">
                            {humanise(charge.kind)}
                          </span>
                          {charge.gates_matriculation && (
                            <Badge tone="brand" className="ml-2">
                              Gating
                            </Badge>
                          )}
                          <p className="mt-0.5 font-mono hint">{charge.session_id}</p>
                        </td>
                        <td className="tabular px-5 py-3 text-right">₦{charge.amount}</td>
                        <td className="tabular px-5 py-3 text-right">₦{charge.allocated}</td>
                        <td className="tabular px-5 py-3 text-right">
                          {charge.is_settled ? (
                            <Badge tone="success">Settled</Badge>
                          ) : (
                            <span className="font-medium text-amber-700 dark:text-amber-400">
                              ₦{charge.outstanding}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card>
            <CardHeader title="Payments received" />
            {account.payments.length === 0 ? (
              <EmptyState title="No payments" description="Nothing has been received yet." />
            ) : (
              <CardBody className="space-y-2">
                {account.payments.map((payment) => (
                  <div
                    key={payment.gateway_ref}
                    className="flex items-center justify-between gap-4 border-b border-ink-100 py-2.5 text-sm last:border-0 dark:border-ink-800"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-mono text-ink-900 dark:text-ink-100">
                        {payment.gateway_ref}
                      </p>
                      <p className="hint">{new Date(payment.received_at).toLocaleString()}</p>
                    </div>
                    <span className="tabular shrink-0 font-medium text-ink-900 dark:text-ink-100">
                      ₦{payment.amount}
                    </span>
                  </div>
                ))}
              </CardBody>
            )}
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Your account" />
            <CardBody>
              <dl>
                <Detail label="Party id" value={account.party_id} mono />
                <Detail label="Matric number" value={account.student_id} mono />
                <Detail label="Programme" value={account.program_id} mono />
                <Detail label="Level" value={account.level} />
                <Detail
                  label="Acceptance fee"
                  value={
                    <Badge tone={account.acceptance_fee_settled ? 'success' : 'warning'}>
                      {account.acceptance_fee_settled ? 'Settled' : 'Outstanding'}
                    </Badge>
                  }
                />
              </dl>
            </CardBody>
          </Card>

          <FormCard
            title="Start a payment"
            description="Opens a checkout against your ledger."
            submitLabel="Start payment"
            mutation={initiate}
            onSubmit={pay}
            successTitle="Checkout opened"
            renderSuccess={(intent) => (
              <span>
                Reference <span className="font-mono">{intent.reference}</span>, expiring{' '}
                {new Date(intent.expires_at).toLocaleString()}.
              </span>
            )}
            footNote="A checkout expires after an hour if nothing arrives. Nothing is owed by opening one."
          >
            <FieldRow>
              <Input
                label="Reference"
                required
                {...bind('reference')}
                hint="The gateway's reference for this payment."
              />
              <Input
                label="Amount"
                required
                inputMode="decimal"
                placeholder="20000.00"
                {...bind('amount')}
              />
            </FieldRow>
          </FormCard>

          <Note tone="info" title="How payments are applied">
            You do not choose which charge a payment settles — the ledger does, taking the charge
            that is holding something up first, then the rest in the order they were raised.
            Anything left over becomes a credit balance.
          </Note>
        </div>
      </div>
    </>
  )
}
