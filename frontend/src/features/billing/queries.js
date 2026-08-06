import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

/**
 * Billing: one ledger per party, from the acceptance fee onwards.
 *
 * **`party_id` is neutral.** Before matriculation it is an applicant id; after, the account is
 * linked to the matric number and the repository resolves either. That is why the bursary's
 * lookup box takes "applicant id or matric number" rather than one of them.
 *
 * **Every amount crosses as a string** and must stay one. They are exact decimals quantized to
 * kobo; parsing them into JavaScript numbers to add them up would reintroduce the error the
 * server's `Decimal` avoids, and money is the one place that is not survivable. Where a total
 * is needed the server has already computed it — `outstanding`, `credit_balance`, `allocated`.
 */

const billing = ['billing']

export const useAccount = (partyId) =>
  useQuery({
    queryKey: [...billing, 'accounts', partyId],
    queryFn: () => api.get(`/billing/accounts/${partyId}`).then((r) => r.data),
    enabled: Boolean(partyId),
    retry: false,
  })

/**
 * Open a checkout against a ledger.
 *
 * The intent's amount is what the student *intends* to pay, and the ledger later records what
 * the gateway *confirms* — a short payment confirms the intent and leaves the charge
 * outstanding, and both are true at once. So the UI never reports "paid" off an intent.
 */
export const useInitiatePayment = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ partyId, reference, amount, initiatedAt, ttlSeconds }) =>
      api
        .post('/billing/payment-intents', {
          party_id: partyId,
          reference,
          amount,
          initiated_at: initiatedAt ?? new Date().toISOString(),
          ...(ttlSeconds ? { ttl_seconds: ttlSeconds } : {}),
        })
        .then((r) => r.data),
    onSuccess: (_, { partyId }) =>
      queryClient.invalidateQueries({ queryKey: [...billing, 'accounts', partyId] }),
  })
}

// ---- university-scoped: the bursary's own acts ----

/**
 * Record a payment directly against a ledger.
 *
 * Idempotent on `gateway_ref`: a duplicate is a no-op, not an error, and comes back tagged
 * `duplicate_ignored`. Both tags are successes and the UI reports which happened rather than
 * treating the second as a failure.
 */
export const useRecordPayment = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ partyId, gatewayRef, amount, receivedAt }) =>
      api
        .post(`/billing/accounts/${partyId}/payments`, {
          gateway_ref: gatewayRef,
          amount,
          received_at: receivedAt ?? new Date().toISOString(),
        })
        .then((r) => r.data),
    onSuccess: (_, { partyId }) =>
      queryClient.invalidateQueries({ queryKey: [...billing, 'accounts', partyId] }),
  })
}

/** Link a ledger opened at acceptance to the matric number its holder was later issued. */
export const useLinkStudentAccount = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ partyId, studentId }) =>
      api
        .post(`/billing/accounts/${partyId}/student-link`, { student_id: studentId })
        .then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: billing }),
  })
}

/**
 * Batch-apply a session's fee schedule to every active account.
 *
 * A `(programme, level)` the schedule does not price is **skipped and reported** rather than
 * failing the batch — so the response's skipped list is the thing worth showing, not an
 * afterthought. A session with no schedule at all refuses outright.
 */
export const useApplySessionFees = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId }) =>
      api.post('/billing/session-fees', { session_id: sessionId }).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: billing }),
  })
}

/**
 * Sweep expired intents, verifying each with the gateway before writing any of them off.
 *
 * "Webhook lost but money taken" is the stuck state this exists to catch. An intent the gateway
 * cannot be reached about comes back under `unreachable` and is left open — the UI shows that
 * list separately from the abandoned one, because they mean opposite things.
 */
export const useReconcile = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ now } = {}) =>
      api.post('/billing/reconciliations', { now: now ?? new Date().toISOString() }).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: billing }),
  })
}
