import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useCourses = (params) =>
  useQuery({
    queryKey: ['courses', params],
    queryFn: () => api.get('/courses', { params }).then((r) => r.data),
  })

export const useCourse = (id) =>
  useQuery({
    queryKey: ['courses', id],
    queryFn: () => api.get(`/courses/${id}`).then((r) => r.data),
    enabled: !!id,
  })

export const useAddCourse = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/courses', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['courses'] }),
  })
}

export const useAddPrerequisite = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ courseId, ...data }) =>
      api.post(`/courses/${courseId}/prerequisites`, data).then((r) => r.data),
    onSuccess: (_, { courseId }) => qc.invalidateQueries({ queryKey: ['courses', courseId] }),
  })
}

// --- Sections ---
export const useSections = (params) =>
  useQuery({
    queryKey: ['sections', params],
    queryFn: () => api.get('/courses/sections', { params }).then((r) => r.data),
  })

export const useAddSection = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/courses/sections', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sections'] }),
  })
}

export const useSectionEnrollments = (sectionId) =>
  useQuery({
    queryKey: ['sections', sectionId, 'enrollments'],
    queryFn: () => api.get(`/courses/sections/${sectionId}/enrollments`).then((r) => r.data),
    enabled: !!sectionId,
  })
