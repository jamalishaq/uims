import { useMemo, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { createColumnHelper } from '@tanstack/react-table'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import Badge from '../../components/ui/Badge'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import { useStudents, useUpdateStudentStatus } from '../../features/students/queries'

const col = createColumnHelper()

const LEVELS = ['100', '200', '300', '400', '500']

const STUDENT_STATUSES = ['active', 'inactive', 'graduated', 'withdrawn', 'suspended']

const STATUS_BADGE = {
  active:    'success',
  inactive:  'warning',
  graduated: 'indigo',
  withdrawn: 'danger',
  suspended: 'danger',
}

function useDebounce(value, delay = 400) {
  const [debounced, setDebounced] = useState(value)
  const timeoutRef = useMemo(() => ({ current: null }), [])

  const update = useCallback(
    (v) => {
      clearTimeout(timeoutRef.current)
      timeoutRef.current = setTimeout(() => setDebounced(v), delay)
    },
    [delay, timeoutRef]
  )

  return [debounced, update]
}

function toErrorMsg(err) {
  return (
    err?.response?.data?.detail ||
    err?.response?.data?.message ||
    err?.message ||
    'Something went wrong'
  )
}

export default function Students() {
  useTitle('Students')
  const navigate = useNavigate()

  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useDebounce('')
  const [programFilter, setProgramFilter] = useState('')
  const [levelFilter, setLevelFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [page, setPage] = useState(1)

  const params = {
    page,
    per_page: 20,
    ...(debouncedSearch ? { q: debouncedSearch } : {}),
    ...(programFilter ? { program_id: programFilter } : {}),
    ...(levelFilter ? { level: levelFilter } : {}),
    ...(statusFilter ? { status: statusFilter } : {}),
  }

  const { data, isLoading } = useStudents(params)
  const { mutate: updateStatus, isPending: isUpdatingStatus } = useUpdateStudentStatus()

  // API returns paginated shape: { items, total, page, per_page, pages }
  const students = data?.items ?? (Array.isArray(data) ? data : [])
  const paginationMeta = data?.items
    ? { page: data.page, per_page: data.per_page, total: data.total, pages: data.pages }
    : null

  const handleSearchChange = (e) => {
    const v = e.target.value
    setSearch(v)
    setDebouncedSearch(v)
    setPage(1)
  }

  const handleStatusChange = (student, newStatus) => {
    updateStatus(
      { id: student.id, status: newStatus },
      {
        onSuccess: () => toast.success(`Status updated to "${newStatus}".`),
        onError: (err) => toast.error(toErrorMsg(err)),
      }
    )
  }

  const columns = useMemo(
    () => [
      col.accessor((row) => row.matric_number ?? row.matricNumber ?? '—', {
        id: 'matric',
        header: 'Matric No.',
      }),
      col.accessor((row) => row.username ?? row.user?.username ?? '—', {
        id: 'username',
        header: 'Username',
      }),
      col.accessor((row) => row.program?.name ?? row.program_name ?? '—', {
        id: 'program',
        header: 'Program',
      }),
      col.accessor((row) => row.level ?? '—', {
        id: 'level',
        header: 'Level',
      }),
      col.accessor('status', {
        header: 'Status',
        cell: ({ getValue }) => {
          const status = getValue() ?? ''
          return (
            <Badge color={STATUS_BADGE[status] ?? 'default'}>
              {status ? status.charAt(0).toUpperCase() + status.slice(1) : '—'}
            </Badge>
          )
        },
      }),
      col.accessor((row) => {
        const cgpa = row.cgpa ?? row.gpa
        return cgpa != null ? Number(cgpa).toFixed(2) : '—'
      }, {
        id: 'cgpa',
        header: 'CGPA',
      }),
      col.display({
        id: 'actions',
        header: '',
        cell: ({ row }) => {
          const student = row.original
          return (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => navigate(`/registrar/students/${student.id}`)}
              >
                View
              </Button>
              <select
                defaultValue=""
                disabled={isUpdatingStatus}
                onChange={(e) => {
                  if (e.target.value) {
                    handleStatusChange(student, e.target.value)
                    e.target.value = ''
                  }
                }}
                className="rounded-lg border border-slate-200 dark:border-slate-700 px-2 py-1.5 text-xs bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:border-indigo-500 focus:ring-indigo-500/20"
              >
                <option value="" disabled>Change status</option>
                {STUDENT_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          )
        },
      }),
    ],
    [isUpdatingStatus, navigate] // eslint-disable-line react-hooks/exhaustive-deps
  )

  return (
    <div>
      <PageHeader title="Students" subtitle="Search, filter and manage registered students." />

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="flex-1 min-w-0">
          <Input
            placeholder="Search by name or matric no…"
            value={search}
            onChange={handleSearchChange}
          />
        </div>
        <Select
          value={levelFilter}
          onChange={(e) => { setLevelFilter(e.target.value); setPage(1) }}
          className="sm:w-36"
        >
          <option value="">All Levels</option>
          {LEVELS.map((l) => (
            <option key={l} value={l}>{l} Level</option>
          ))}
        </Select>
        <Select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          className="sm:w-40"
        >
          <option value="">All Statuses</option>
          {STUDENT_STATUSES.map((s) => (
            <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
          ))}
        </Select>
      </div>

      <Table
        columns={columns}
        data={students}
        isLoading={isLoading}
        emptyMessage="No students found."
        pagination={
          paginationMeta
            ? { ...paginationMeta, onPageChange: setPage }
            : undefined
        }
      />
    </div>
  )
}
