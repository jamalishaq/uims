import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useStaff = (params) =>
  useQuery({
    queryKey: ['staff', params],
    queryFn: () => api.get('/staff', { params }).then((r) => r.data),
  })

export const useAddStaff = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/staff', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['staff'] }),
  })
}
