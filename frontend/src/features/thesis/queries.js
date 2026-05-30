import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useThesis = () =>
  useQuery({
    queryKey: ['thesis'],
    queryFn: () => api.get('/thesis').then((r) => r.data),
  })

export const useMyThesis = () =>
  useQuery({
    queryKey: ['thesis', 'my'],
    queryFn: () => api.get('/thesis/my').then((r) => r.data),
    retry: (failureCount, err) => {
      if (err?.response?.status === 404) return false
      return failureCount < 2
    },
  })

export const useRegisterThesis = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/thesis', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['thesis'] }),
  })
}

export const useSubmitThesis = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }) =>
      api.post(`/thesis/${id}/submit`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['thesis'] }),
  })
}

export const useReviewThesis = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }) =>
      api.post(`/thesis/${id}/review`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['thesis'] }),
  })
}
