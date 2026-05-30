import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useStudents = (params) =>
  useQuery({
    queryKey: ['students', params],
    queryFn: () => api.get('/students', { params }).then((r) => r.data),
  })

export const useStudent = (id) =>
  useQuery({
    queryKey: ['students', id],
    queryFn: () => api.get(`/students/${id}`).then((r) => r.data),
    enabled: !!id,
  })

export const useUpdateStudentStatus = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }) =>
      api.patch(`/students/${id}/status`, data).then((r) => r.data),
    onSuccess: (_, { id }) => qc.invalidateQueries({ queryKey: ['students', id] }),
  })
}
