import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useApplications = (params) =>
  useQuery({
    queryKey: ['applications', params],
    queryFn: () => api.get('/admission/applications', { params }).then((r) => r.data),
  })

export const useApplication = (id) =>
  useQuery({
    queryKey: ['applications', id],
    queryFn: () => api.get(`/admission/applications/${id}`).then((r) => r.data),
    enabled: !!id,
  })

export const useApply = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/admission/apply', data).then((r) => r.data),
    onSuccess: (data) => {
      // Cache the applicant's own application so ApplicationStatus can display it
      qc.setQueryData(['applications', 'mine'], data)
      qc.invalidateQueries({ queryKey: ['applications'] })
    },
  })
}

// Read-only hook for the applicant to check their cached application (no server fetch —
// the API endpoint is registrar-only; we rely on the data stored by useApply on success)
export const useMyApplication = () =>
  useQuery({
    queryKey: ['applications', 'mine'],
    queryFn: () => null,   // no real endpoint; data is populated by useApply onSuccess
    staleTime: Infinity,
    retry: false,
  })

export const useDecideApplication = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }) =>
      api.post(`/admission/applications/${id}/decision`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['applications'] }),
  })
}

export const useEnrollApplicant = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id) =>
      api.post(`/admission/applications/${id}/enroll`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['applications'] }),
  })
}
