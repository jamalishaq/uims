import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useMyGrades = () =>
  useQuery({
    queryKey: ['grades', 'me'],
    queryFn: () => api.get('/grades/me').then((r) => r.data),
  })

export const useTranscript = (studentId) =>
  useQuery({
    queryKey: ['grades', 'transcript', studentId],
    queryFn: () => api.get(`/grades/transcript/${studentId}`).then((r) => r.data),
    enabled: !!studentId,
  })

export const useSubmitGrade = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ enrollmentId, ...data }) =>
      api.post(`/grades/${enrollmentId}`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['grades'] }),
  })
}
