import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'

export const useBooks = (params) =>
  useQuery({
    queryKey: ['library', 'books', params],
    queryFn: () => api.get('/library/books', { params }).then((r) => r.data),
  })

export const useMyBorrowings = () =>
  useQuery({
    queryKey: ['library', 'my-borrowings'],
    queryFn: () => api.get('/library/my-borrowings').then((r) => r.data),
  })

export const useBorrowBook = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data) => api.post('/library/borrow', data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library'] }),
  })
}

export const useReturnBook = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (borrowingId) => api.post(`/library/return/${borrowingId}`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['library'] }),
  })
}
