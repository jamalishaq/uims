import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useHostels = () =>
  useQuery({
    queryKey: ['hostel'],
    queryFn: () => api.get('/hostel').then((r) => r.data),
  })

export const useApplyHostel = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/hostel/apply', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hostel'] }),
  })
}

export const useAllocateRoom = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/hostel/allocate', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['hostel'] }),
  })
}
