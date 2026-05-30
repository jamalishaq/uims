import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useExamTimetable = (params) =>
  useQuery({
    queryKey: ['exams', 'timetable', params],
    queryFn: () => api.get('/exams/timetable', { params }).then((r) => r.data),
  })

export const useExamSlots = (params) =>
  useQuery({
    queryKey: ['exams', 'slots', params],
    queryFn: () => api.get('/exams', { params }).then((r) => r.data),
  })

export const useAddExamSlot = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/exams/timetable', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['exams'] }),
  })
}
