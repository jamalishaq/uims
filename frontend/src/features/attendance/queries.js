import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useMyAttendance = () =>
  useQuery({
    queryKey: ['attendance', 'me'],
    queryFn: () => api.get('/attendance/my').then((r) => r.data),
  })

export const useAttendanceSummary = (sectionId) =>
  useQuery({
    queryKey: ['attendance', 'summary', sectionId],
    queryFn: () => api.get(`/attendance/sections/${sectionId}/summary`).then((r) => r.data),
    enabled: !!sectionId,
  })

export const useMarkAttendance = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ sectionId, ...data }) =>
      api.post(`/attendance/sections/${sectionId}`, data).then((r) => r.data),
    onSuccess: (_, { sectionId }) =>
      qc.invalidateQueries({ queryKey: ['attendance', 'summary', sectionId] }),
  })
}
