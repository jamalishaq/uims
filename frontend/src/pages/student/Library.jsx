import { useMemo, useState, useCallback } from 'react'
import toast from 'react-hot-toast'
import { createColumnHelper } from '@tanstack/react-table'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import { useBooks, useMyBorrowings, useBorrowBook, useReturnBook } from '../../features/library/queries'

const col = createColumnHelper()

function useDebounce(value, delay = 400) {
  const [debounced, setDebounced] = useState(value)
  const timeoutRef = useMemo(() => ({ current: null }), [])

  const update = useCallback(
    (val) => {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = setTimeout(() => setDebounced(val), delay)
    },
    [delay, timeoutRef]
  )

  return [debounced, update]
}

export default function Library() {
  useTitle('Library')

  const [searchInput, setSearchInput] = useState('')
  const [debouncedQ, setDebouncedQ] = useDebounce('', 400)
  const [borrowingBook, setBorrowingBook] = useState(null)
  const [returningId, setReturningId] = useState(null)

  const handleSearch = (e) => {
    const val = e.target.value
    setSearchInput(val)
    setDebouncedQ(val)
  }

  const params = debouncedQ ? { q: debouncedQ } : undefined
  const { data: books = [], isLoading: loadingBooks } = useBooks(params)
  const { data: borrowings = [], isLoading: loadingBorrowings } = useMyBorrowings()
  const { mutate: borrowBook } = useBorrowBook()
  const { mutate: returnBook } = useReturnBook()

  const handleBorrow = (book) => {
    setBorrowingBook(book.id)
    borrowBook(
      { book_id: book.id },
      {
        onSuccess: () => {
          toast.success(`"${book.title}" borrowed successfully.`)
          setBorrowingBook(null)
        },
        onError: (err) => {
          const msg =
            err?.response?.data?.detail ??
            err?.response?.data?.message ??
            err?.message ??
            'Failed to borrow book.'
          toast.error(msg)
          setBorrowingBook(null)
        },
      }
    )
  }

  const handleReturn = (borrowingId, title) => {
    setReturningId(borrowingId)
    returnBook(borrowingId, {
      onSuccess: () => {
        toast.success(`"${title}" returned successfully.`)
        setReturningId(null)
      },
      onError: (err) => {
        const msg =
          err?.response?.data?.detail ??
          err?.response?.data?.message ??
          err?.message ??
          'Failed to return book.'
        toast.error(msg)
        setReturningId(null)
      },
    })
  }

  const bookColumns = useMemo(
    () => [
      col.accessor((row) => row.title ?? '—', { id: 'title', header: 'Title' }),
      col.accessor((row) => row.author ?? '—', { id: 'author', header: 'Author' }),
      col.accessor((row) => row.isbn ?? '—', { id: 'isbn', header: 'ISBN' }),
      col.display({
        id: 'available_copies',
        header: 'Available Copies',
        cell: ({ row }) => {
          const copies = row.original.available_copies ?? 0
          return (
            <span
              className={
                copies > 0
                  ? 'text-emerald-600 dark:text-emerald-400 font-medium'
                  : 'text-red-500 dark:text-red-400 font-medium'
              }
            >
              {copies}
            </span>
          )
        },
      }),
      col.display({
        id: 'actions',
        header: '',
        cell: ({ row }) => {
          const book = row.original
          const available = (book.available_copies ?? 0) > 0
          const isBorrowing = borrowingBook === book.id
          return (
            <Button
              size="sm"
              variant="primary"
              disabled={!available || !!borrowingBook}
              loading={isBorrowing}
              onClick={() => handleBorrow(book)}
            >
              Borrow
            </Button>
          )
        },
      }),
    ],
    [borrowingBook]
  )

  const borrowingColumns = useMemo(
    () => [
      col.accessor(
        (row) => row.book?.title ?? row.book_title ?? String(row.book_id ?? '—'),
        { id: 'title', header: 'Book Title' }
      ),
      col.accessor(
        (row) => row.book?.author ?? row.author ?? '—',
        { id: 'author', header: 'Author' }
      ),
      col.display({
        id: 'borrowed_at',
        header: 'Borrowed On',
        cell: ({ row }) => {
          const d = row.original.borrowed_at ?? row.original.created_at
          if (!d) return '—'
          try {
            return new Date(d).toLocaleDateString('en-GB', {
              day: '2-digit',
              month: 'short',
              year: 'numeric',
            })
          } catch {
            return d
          }
        },
      }),
      col.display({
        id: 'due_date',
        header: 'Due Date',
        cell: ({ row }) => {
          const d = row.original.due_date ?? row.original.return_by
          if (!d) return '—'
          try {
            return new Date(d).toLocaleDateString('en-GB', {
              day: '2-digit',
              month: 'short',
              year: 'numeric',
            })
          } catch {
            return d
          }
        },
      }),
      col.display({
        id: 'return_action',
        header: '',
        cell: ({ row }) => {
          const b = row.original
          const isReturning = returningId === b.id
          const title = b.book?.title ?? b.book_title ?? 'book'
          return (
            <Button
              size="sm"
              variant="secondary"
              loading={isReturning}
              disabled={!!returningId}
              onClick={() => handleReturn(b.id, title)}
            >
              Return
            </Button>
          )
        },
      }),
    ],
    [returningId]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Library"
        subtitle="Search for books and manage your borrowings."
      />

      {/* Search */}
      <div className="max-w-md">
        <Input
          placeholder="Search by title, author, or ISBN…"
          value={searchInput}
          onChange={handleSearch}
        />
      </div>

      {/* Books table */}
      <Table
        columns={bookColumns}
        data={books}
        isLoading={loadingBooks}
        emptyMessage="No books found."
      />

      {/* My borrowings */}
      <div>
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3">
          My Borrowings
        </h2>
        <Table
          columns={borrowingColumns}
          data={borrowings}
          isLoading={loadingBorrowings}
          emptyMessage="You have no active borrowings."
        />
      </div>
    </div>
  )
}
