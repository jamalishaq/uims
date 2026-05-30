import { useQuery } from '@tanstack/react-query'
import api from '../../lib/api'

export const useEnrollmentStats = (params) =>
  useQuery({
    queryKey: ['reports', 'enrollment-stats', params],
    queryFn: () => api.get('/reports/enrollment-stats', { params }).then((r) => r.data),
  })

export const usePassFailRates = (params) =>
  useQuery({
    queryKey: ['reports', 'pass-fail', params],
    queryFn: () => api.get('/reports/pass-fail', { params }).then((r) => r.data),
  })

export const useFeeCollection = (params) =>
  useQuery({
    queryKey: ['reports', 'fee-collection', params],
    queryFn: () => api.get('/reports/fee-collection', { params }).then((r) => r.data),
  })

export const useCgpaDistribution = (params) =>
  useQuery({
    queryKey: ['reports', 'cgpa-distribution', params],
    queryFn: () => api.get('/reports/cgpa-distribution', { params }).then((r) => r.data),
  })
