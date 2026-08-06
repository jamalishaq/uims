import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

/** Course Catalog: slow-changing reference data, with no notion of a specific student. */

const catalog = ['course-catalog']

export const useDepartmentCourses = (departmentId, includeRetired = false) =>
  useQuery({
    queryKey: [...catalog, 'departments', departmentId, { includeRetired }],
    queryFn: () =>
      api
        .get(`/course-catalog/departments/${departmentId}/courses`, {
          params: { include_retired: includeRetired },
        })
        .then((r) => r.data),
    enabled: Boolean(departmentId),
  })

export const useCourse = (courseId) =>
  useQuery({
    queryKey: [...catalog, 'courses', courseId],
    queryFn: () => api.get(`/course-catalog/courses/${courseId}`).then((r) => r.data),
    enabled: Boolean(courseId),
    retry: false,
  })

export const usePrerequisiteChain = (courseId) =>
  useQuery({
    queryKey: [...catalog, 'courses', courseId, 'prerequisite-chain'],
    queryFn: () =>
      api.get(`/course-catalog/courses/${courseId}/prerequisite-chain`).then((r) => r.data),
    enabled: Boolean(courseId),
    retry: false,
  })

export const useRegisterCourse = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body) => api.post('/course-catalog/courses', body).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalog }),
  })
}

export const useAmendCourse = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ courseId, ...body }) =>
      api.patch(`/course-catalog/courses/${courseId}`, body).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalog }),
  })
}

/**
 * Retiring is reversible and does not remove the course.
 *
 * A retired course must keep resolving for Academic Records, because transcripts refer to
 * courses no longer taught. So this is a state, not a delete, and the UI shows retired courses
 * behind a toggle rather than hiding them for good.
 */
export const useRetireCourse = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (courseId) =>
      api.post(`/course-catalog/courses/${courseId}/retirement`).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalog }),
  })
}

export const useReinstateCourse = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (courseId) =>
      api.delete(`/course-catalog/courses/${courseId}/retirement`).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalog }),
  })
}

export const useAddPrerequisite = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ courseId, prerequisiteId }) =>
      api
        .put(`/course-catalog/courses/${courseId}/prerequisites/${prerequisiteId}`)
        .then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalog }),
  })
}

export const useRemovePrerequisite = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ courseId, prerequisiteId }) =>
      api
        .delete(`/course-catalog/courses/${courseId}/prerequisites/${prerequisiteId}`)
        .then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: catalog }),
  })
}
