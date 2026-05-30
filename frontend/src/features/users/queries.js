import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useUsers = (params) =>
  useQuery({
    queryKey: ['users', params],
    queryFn: () => api.get('/users', { params }).then((r) => r.data),
  })

export const useToggleUserActive = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (userId) => api.patch(`/users/${userId}/toggle-active`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })
}
