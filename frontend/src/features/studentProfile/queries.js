import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

/**
 * Student Profile: the identity anchor, deliberately thin.
 *
 * There is no route that returns "everything about a student" and there is not going to be —
 * a student's record, ledger and registrations belong to Academic Records, Billing and
 * Enrollment, and a read here that assembled them would be one module knowing four contexts.
 * The student dashboard composes them from those three, which is the client doing what only a
 * client may.
 *
 * There is also **no route that changes a level**: what advances one and when is an
 * institutional fact nobody has stated, so no form here offers it.
 */

const profile = ['student-profile']

export const useStudent = (studentId) =>
  useQuery({
    queryKey: [...profile, 'students', studentId],
    queryFn: () => api.get(`/student-profile/students/${studentId}`).then((r) => r.data),
    enabled: Boolean(studentId),
    retry: false,
  })

/**
 * The other two names a student has.
 *
 * `applicantId` is how a client follows a matriculation to the student it produced — nothing is
 * published back to Admissions, so the matric number cannot be learned there. Exactly one of
 * the two must be given; the API answers 422 for both or neither.
 */
export const useFindStudent = ({ matricNumber, applicantId } = {}) =>
  useQuery({
    queryKey: [...profile, 'find', matricNumber ?? applicantId],
    queryFn: () =>
      api
        .get('/student-profile/students', {
          params: matricNumber ? { matric_number: matricNumber } : { applicant_id: applicantId },
        })
        .then((r) => r.data),
    enabled: Boolean(matricNumber) !== Boolean(applicantId),
    retry: false,
  })

/**
 * Register a student by hand — the path for somebody who never went through Admissions.
 *
 * The matric number is **not** in the request and cannot be: it is composed from the
 * department's numeric code and the entry year against a counter that survives restarts,
 * precisely so two students never share one.
 */
export const useRegisterStudent = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body) => api.post('/student-profile/students', body).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: profile }),
  })
}

/**
 * Fix what the university got wrong about a person.
 *
 * A replacement, not a patch: omitted optional fields clear. The matric number does not move —
 * it encodes entry year and department, neither of which a spelling touches.
 */
export const useCorrectBioData = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ studentId, ...body }) =>
      api.put(`/student-profile/students/${studentId}/bio-data`, body).then((r) => r.data),
    onSuccess: (_, { studentId }) =>
      queryClient.invalidateQueries({ queryKey: [...profile, 'students', studentId] }),
  })
}
