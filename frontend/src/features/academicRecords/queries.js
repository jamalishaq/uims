import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

/**
 * Academic Records: the transcript, its CGPA, and the standing that follows.
 *
 * Two routes, and both are keyed by `student_id`. A student reads their own with the id in
 * their token's scope; a registrar reads anybody's.
 *
 * **Every number crosses as a string** — CGPAs, GPAs, grade points. That is deliberate on the
 * server's side and must not be "fixed" here: they are exact decimals quantized to two places,
 * and parsing them into JavaScript floats to render them would reintroduce the rounding the
 * server went out of its way to avoid. Render them as they arrive.
 */

const records = ['academic-records']

export const useAcademicRecord = (studentId) =>
  useQuery({
    queryKey: [...records, studentId],
    queryFn: () => api.get(`/academic-records/records/${studentId}`).then((r) => r.data),
    enabled: Boolean(studentId),
    retry: false,
  })

/**
 * Correct a mark already recorded. Administrative, and never the submitting lecturer's.
 *
 * It appends rather than overwrites: the previous score, the reason and the authoriser all stay
 * on the record. `authorisedBy` names who inside the university authorised it — which is not
 * always who typed it, so the form asks rather than filling it in from the token.
 */
export const useCorrectGrade = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ studentId, courseId, semesterId, score, reason, authorisedBy }) =>
      api
        .post(`/academic-records/records/${studentId}/corrections`, {
          course_id: courseId,
          semester_id: semesterId,
          score,
          reason,
          authorised_by: authorisedBy,
        })
        .then((r) => r.data),
    onSuccess: (_, { studentId }) =>
      queryClient.invalidateQueries({ queryKey: [...records, studentId] }),
  })
}
