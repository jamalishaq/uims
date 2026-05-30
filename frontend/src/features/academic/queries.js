import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

// --- Faculties ---
export const useFaculties = () =>
  useQuery({ queryKey: ['faculties'], queryFn: () => api.get('/academic/faculties').then((r) => r.data) })

export const useAddFaculty = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/academic/faculties', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['faculties'] }),
  })
}

// --- Departments ---
export const useDepartments = (params) =>
  useQuery({
    queryKey: ['departments', params],
    queryFn: () => api.get('/academic/departments', { params }).then((r) => r.data),
  })

export const useAddDepartment = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/academic/departments', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['departments'] }),
  })
}

// --- Programs ---
export const usePrograms = (params) =>
  useQuery({
    queryKey: ['programs', params],
    queryFn: () => api.get('/academic/programs', { params }).then((r) => r.data),
  })

export const useAddProgram = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/academic/programs', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['programs'] }),
  })
}

// --- Sessions & Semesters ---
export const useSessions = () =>
  useQuery({ queryKey: ['sessions'], queryFn: () => api.get('/academic/sessions').then((r) => r.data) })

export const useAddSession = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/academic/sessions', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  })
}

export const useAddSemester = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId, ...data }) =>
      api.post(`/academic/sessions/${sessionId}/semesters`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sessions'] }),
  })
}
