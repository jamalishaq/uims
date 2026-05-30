import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useMyFees = () =>
  useQuery({
    queryKey: ['fees', 'me'],
    queryFn: () => api.get('/payments/fees').then((r) => r.data),
  })

export const useFeeSchedule = (params) =>
  useQuery({
    queryKey: ['fees', 'schedule', params],
    queryFn: () => api.get('/payments/schedule', { params }).then((r) => r.data),
  })

export const useCreateFeeSchedule = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/payments/schedule', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['fees', 'schedule'] }),
  })
}

export const useGeneratePayments = () =>
  useMutation({
    mutationFn: (params) => api.post('/payments/generate', null, { params }).then((r) => r.data),
  })

export const useInitPayment = () =>
  useMutation({
    mutationFn: (data) => api.post('/payments/initialize', data).then((r) => r.data),
  })

export const useVerifyPayment = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (reference) => api.post(`/payments/verify/${reference}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['fees'] }),
  })
}
