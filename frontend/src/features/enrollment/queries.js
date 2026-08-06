import { useMutation } from '@tanstack/react-query'
import api from '../../lib/api'

/**
 * Enrollment: one route, and it is a POST.
 *
 * There is no way to list a student's registrations over HTTP — the context has a single
 * inbound route. So the registration page shows the outcome of what you just submitted and does
 * not pretend to show a register; a table of "my courses" would have to be assembled from
 * something, and there is nothing to assemble it from.
 *
 * The one thing this page must get right is that **a refusal is a 200**. It is a decision the
 * university made about a request it understood, and it can have four separate causes at once —
 * prerequisites unmet, credit cap exceeded, no seat, not financially cleared. The body carries
 * every unmet reason rather than the first, which is why the UI lists them.
 */
export const useRegisterForCourse = () =>
  useMutation({
    mutationFn: ({
      enrollmentId,
      studentId,
      courseId,
      sessionId,
      semesterId,
      semesterOrdinal,
    }) =>
      api
        .post('/enrollment/registrations', {
          enrollment_id: enrollmentId,
          student_id: studentId,
          course_id: courseId,
          session_id: sessionId,
          semester_id: semesterId,
          // No default, deliberately: Billing's clearance rule differs between the two halves
          // of a session (≥70% then 100%), so a caller that omitted this would be asking about
          // the wrong half and getting a confident answer.
          semester_ordinal: semesterOrdinal,
        })
        .then((r) => r.data),
  })

/**
 * Whether a registration response is the accepted branch.
 *
 * The tag is `'accepted'` / `'refused'` — read off the server's `Literal` rather than guessed,
 * because both branches are 200 and a wrong string here would render every refusal as a success.
 */
export const wasAccepted = (outcome) => outcome?.outcome === 'accepted'
