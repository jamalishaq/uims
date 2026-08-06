import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

/**
 * Faculty & Department: structure, the academic calendar, and lecturers.
 *
 * **There is no route that lists faculties, departments or sessions**, and that is not an
 * oversight in this file. The API has `POST /faculties`, `POST /departments`, `POST /programs`
 * and `POST /sessions`, plus reads keyed by an id you already hold — `GET
 * /departments/{id}/programs`, `GET /departments/{id}/lecturers`, `GET
 * /programs/{id}/placement`. Nothing enumerates the top of the tree.
 *
 * That shapes the UI rather than being worked around: the structure page asks for a department
 * id rather than offering a dropdown of them, because a dropdown would need a list route that
 * does not exist and inventing one client-side means keeping a second copy of the university's
 * structure in this app. Where a page needs a starting point, it uses the signed-in principal's
 * own `scopeId` — which a faculty officer and a department registrar always have.
 */

const structure = ['faculty-department']

export const useDepartmentPrograms = (departmentId) =>
  useQuery({
    queryKey: [...structure, 'departments', departmentId, 'programs'],
    queryFn: () =>
      api.get(`/faculty-department/departments/${departmentId}/programs`).then((r) => r.data),
    enabled: Boolean(departmentId),
  })

export const useDepartmentLecturers = (departmentId) =>
  useQuery({
    queryKey: [...structure, 'departments', departmentId, 'lecturers'],
    queryFn: () =>
      api.get(`/faculty-department/departments/${departmentId}/lecturers`).then((r) => r.data),
    enabled: Boolean(departmentId),
  })

export const useLecturer = (lecturerId) =>
  useQuery({
    queryKey: [...structure, 'lecturers', lecturerId],
    queryFn: () => api.get(`/faculty-department/lecturers/${lecturerId}`).then((r) => r.data),
    enabled: Boolean(lecturerId),
  })

export const useProgramPlacement = (programId, sessionId) =>
  useQuery({
    queryKey: [...structure, 'programs', programId, 'placement', sessionId],
    queryFn: () =>
      api
        .get(`/faculty-department/programs/${programId}/placement`, {
          params: { session_id: sessionId },
        })
        .then((r) => r.data),
    enabled: Boolean(programId && sessionId),
    retry: false,
  })

// ---- writes ----

export const useCreateFaculty = () =>
  useMutation({
    mutationFn: (body) => api.post('/faculty-department/faculties', body).then((r) => r.data),
  })

export const useCreateDepartment = () =>
  useMutation({
    mutationFn: (body) => api.post('/faculty-department/departments', body).then((r) => r.data),
  })

export const useCreateProgram = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body) => api.post('/faculty-department/programs', body).then((r) => r.data),
    onSuccess: (_, body) =>
      queryClient.invalidateQueries({
        queryKey: [...structure, 'departments', body.department_id, 'programs'],
      }),
  })
}

/**
 * Open or close a programme's admissions window.
 *
 * A programme is created *not* admitting, and this is the only thing that moves the flag — so a
 * programme cannot start taking applications as a side effect of being described.
 */
export const useSetProgramAdmissions = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ programId, isAdmitting }) =>
      api
        .put(`/faculty-department/programs/${programId}/admissions`, { is_admitting: isAdmitting })
        .then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: structure }),
  })
}

export const usePlanSession = () =>
  useMutation({
    mutationFn: (body) => api.post('/faculty-department/sessions', body).then((r) => r.data),
  })

/**
 * Opening a session is **not** a status flip: it bills a cohort.
 *
 * Billing batch-applies the session's fee schedule to every active account on `SessionOpened`,
 * and this route is the only publisher of it in the system. The UI says so at the point of the
 * click, because "open" reads like a toggle and this one sends invoices.
 */
export const useOpenSession = () =>
  useMutation({
    mutationFn: (sessionId) =>
      api.post(`/faculty-department/sessions/${sessionId}/opening`).then((r) => r.data),
  })

export const useRegisterLecturer = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body) => api.post('/faculty-department/lecturers', body).then((r) => r.data),
    onSuccess: (_, body) =>
      queryClient.invalidateQueries({
        queryKey: [...structure, 'departments', body.department_id, 'lecturers'],
      }),
  })
}

export const useAmendLecturerProfile = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ lecturerId, ...body }) =>
      api.put(`/faculty-department/lecturers/${lecturerId}/profile`, body).then((r) => r.data),
    onSuccess: (_, { lecturerId }) =>
      queryClient.invalidateQueries({ queryKey: [...structure, 'lecturers', lecturerId] }),
  })
}

/**
 * Assigning a course is what makes grade submission reachable at all.
 *
 * `SubmitGrade` authorizes against exactly this: without an assignment, a lecturer created
 * through the API teaches nothing and the grade route answers 403 to everybody.
 */
export const useAssignLecturerToCourse = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ lecturerId, courseId, sessionId }) =>
      api
        .put(`/faculty-department/lecturers/${lecturerId}/courses/${courseId}`, {
          session_id: sessionId,
        })
        .then((r) => r.data),
    onSuccess: (_, { lecturerId }) =>
      queryClient.invalidateQueries({ queryKey: [...structure, 'lecturers', lecturerId] }),
  })
}

export const useWithdrawLecturerFromCourse = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ lecturerId, courseId, sessionId }) =>
      api
        .delete(`/faculty-department/lecturers/${lecturerId}/courses/${courseId}`, {
          params: { session_id: sessionId },
        })
        .then((r) => r.data),
    onSuccess: (_, { lecturerId }) =>
      queryClient.invalidateQueries({ queryKey: [...structure, 'lecturers', lecturerId] }),
  })
}

export const useSubmitGrade = () =>
  useMutation({
    mutationFn: (body) =>
      api.post('/faculty-department/grade-submissions', body).then((r) => r.data),
  })
