import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useAssignments = (params) =>
  useQuery({
    queryKey: ['assignments', params],
    queryFn: () => api.get('/assignments', { params }).then((r) => r.data),
  })

export const useAssignment = (id) =>
  useQuery({
    queryKey: ['assignments', id],
    queryFn: () => api.get(`/assignments/${id}`).then((r) => r.data),
    enabled: !!id,
  })

export const useAddAssignment = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/assignments', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assignments'] }),
  })
}

export const useSubmitAssignment = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }) =>
      api.post(`/assignments/${id}/submit`, data).then((r) => r.data),
    onSuccess: (_, { id }) => qc.invalidateQueries({ queryKey: ['assignments', id] }),
  })
}

export const useGradeAssignment = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, submissionId, ...data }) =>
      api.post(`/assignments/${id}/submissions/${submissionId}/grade`, data).then((r) => r.data),
    onSuccess: (_, { id }) => qc.invalidateQueries({ queryKey: ['assignments', id] }),
  })
}

export const useSubmissions = (assignmentId) =>
  useQuery({
    queryKey: ['assignments', assignmentId, 'submissions'],
    queryFn: () => api.get(`/assignments/${assignmentId}/submissions`).then((r) => r.data),
    enabled: !!assignmentId,
  })
