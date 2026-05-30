import { useQuery } from '@tanstack/react-query'
import api from '../../lib/api'

export const useTranscript = (studentId) =>
  useQuery({
    queryKey: ['transcript', studentId],
    queryFn: () => api.get(`/grades/transcript/${studentId}`).then((r) => r.data),
    enabled: !!studentId,
  })
