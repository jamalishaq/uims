import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

/**
 * Admissions: the policy a registrar publishes, and an application's life.
 *
 * Everything here is keyed by `(program_id, session_id)`, because that is how Admissions holds
 * every fact about a programme. There is no route keyed by department, and a client cannot ask
 * "everything my department is admitting for" in one call — it reads the department's
 * programmes from Faculty & Department first, then asks here per programme. Two calls, and
 * Admissions is spared a notion of departments it has no other reason to hold.
 */

const admissions = ['admissions']

export const useAdmissionCycle = (programId, sessionId) =>
  useQuery({
    queryKey: [...admissions, 'cycle', programId, sessionId],
    queryFn: () =>
      api
        .get(`/admissions/programs/${programId}/admission-cycle`, {
          params: { session_id: sessionId },
        })
        .then((r) => r.data),
    enabled: Boolean(programId && sessionId),
    retry: false,
  })

export const useEntryRequirement = (programId, sessionId) =>
  useQuery({
    queryKey: [...admissions, 'entry-requirement', programId, sessionId],
    queryFn: () =>
      api
        .get(`/admissions/programs/${programId}/entry-requirement`, {
          params: { session_id: sessionId },
        })
        .then((r) => r.data),
    enabled: Boolean(programId && sessionId),
    retry: false,
  })

export const useAlternativePolicy = (programId, sessionId) =>
  useQuery({
    queryKey: [...admissions, 'alternative-policy', programId, sessionId],
    queryFn: () =>
      api
        .get(`/admissions/programs/${programId}/alternative-policy`, {
          params: { session_id: sessionId },
        })
        .then((r) => r.data),
    enabled: Boolean(programId && sessionId),
    retry: false,
  })

/**
 * The registrar's dashboard figure — and it counts a different population from the cycle.
 *
 * `AdmissionCycle.offers_made` counts places claimed *on* a programme, including by applicants
 * who applied elsewhere and overflowed in through a fallback chain. This funnel counts
 * applicants who applied *to* it, including ones eventually placed somewhere else. Both are
 * needed; they do not add up; and reporting either as the other is how a department finds out
 * in September that it admitted people it never saw. The UI labels them capacity and cohort.
 */
export const useAdmissionsSummary = (programId, sessionId) =>
  useQuery({
    queryKey: [...admissions, 'summary', programId, sessionId],
    queryFn: () =>
      api
        .get(`/admissions/programs/${programId}/admissions-summary`, {
          params: { session_id: sessionId },
        })
        .then((r) => r.data),
    enabled: Boolean(programId && sessionId),
  })

/** The working list, keyed on the **applied** programme so the offer flow cannot lose anybody. */
export const useProgramApplicants = (programId, sessionId, status) =>
  useQuery({
    queryKey: [...admissions, 'applicants', programId, sessionId, status ?? 'all'],
    queryFn: () =>
      api
        .get(`/admissions/programs/${programId}/applicants`, {
          params: { session_id: sessionId, ...(status ? { status } : {}) },
        })
        .then((r) => r.data),
    enabled: Boolean(programId && sessionId),
  })

// ---- policy, published once per (programme, session) ----
//
// None of these three overwrites. A second write for the same key is a duplicate and a 409,
// because reopening a cycle would reset `offers_made` and re-sell held places, and republishing
// a rule would judge one cohort by two standards. The forms say so rather than letting somebody
// discover it from a conflict.

export const useOpenAdmissionCycle = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body) => api.post('/admissions/admission-cycles', body).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: admissions }),
  })
}

export const usePublishEntryRequirement = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body) => api.post('/admissions/entry-requirements', body).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: admissions }),
  })
}

export const usePublishAlternativePolicy = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body) => api.post('/admissions/alternative-policies', body).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: admissions }),
  })
}

// ---- an application's life ----

export const useSubmitApplication = () =>
  useMutation({
    mutationFn: (body) => api.post('/admissions/applications', body).then((r) => r.data),
  })

/**
 * Screening and offering both answer **200 with a discriminated body**, never a 4xx.
 *
 * "Not qualified" and "no offer available" are decisions the university made about a request it
 * understood, not malformed requests — so callers read `outcome` rather than catching. A page
 * that treated them as errors would contradict the layer that decided they are not.
 */
const applicantAction = (path) => {
  const useAction = () => {
    const queryClient = useQueryClient()
    return useMutation({
      mutationFn: (applicantId) =>
        api.post(`/admissions/applicants/${applicantId}/${path}`).then((r) => r.data),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: admissions }),
    })
  }
  return useAction
}

export const useScreenApplicant = applicantAction('screening')
export const useMakeOffer = applicantAction('offer')
export const useAcceptOffer = applicantAction('acceptance')
export const useDeclineOffer = applicantAction('declination')

/**
 * Matriculation is human-triggered and gated on the acceptance fee having cleared.
 *
 * Never automatic on payment: paying sets a flag, and this is the act that reads it.
 */
export const useMatriculateApplicant = applicantAction('matriculation')
