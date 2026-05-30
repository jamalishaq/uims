import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useHostels = () =>
  useQuery({
    queryKey: ['hostel'],
    queryFn: () => api.get('/hostel').then((r) => r.data),
  })

export const useMyHostelAllocation = () =>
  useQuery({
    queryKey: ['hostel', 'my-allocation'],
    queryFn: () => api.get('/hostel/my-allocation').then((r) => r.data),
    retry: (failureCount, err) => {
      if (err?.response?.status === 404) return false
      return failureCount < 2
    },
  })

export const useAvailableRooms = () =>
  useQuery({
    queryKey: ['hostel', 'rooms', 'available'],
    queryFn: () => api.get('/hostel/rooms', { params: { available_only: true } }).then((r) => r.data),
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
