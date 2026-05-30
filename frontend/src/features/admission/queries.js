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
    onSuccess: () => qc.invalidateQueries({ queryKey: ['applications'] }),
  })
}

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
