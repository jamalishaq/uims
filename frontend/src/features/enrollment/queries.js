import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useMyEnrollments = () =>
  useQuery({
    queryKey: ['enrollment'],
    queryFn: () => api.get('/enrollment').then((r) => r.data),
  })

export const useEnroll = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/enrollment', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrollment'] }),
  })
}

export const useDropCourse = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (enrollmentId) => api.delete(`/enrollment/${enrollmentId}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrollment'] }),
  })
}
