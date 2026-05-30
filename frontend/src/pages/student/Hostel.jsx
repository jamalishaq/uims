import { useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { createColumnHelper } from '@tanstack/react-table'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Table from '../../components/ui/Table'
import Button from '../../components/ui/Button'
import Select from '../../components/ui/Select'
import {
  useMyHostelAllocation,
  useAvailableRooms,
  useApplyHostel,
} from '../../features/hostel/queries'
import { useSessions } from '../../features/academic/queries'

const col = createColumnHelper()

const ROOM_TYPES = [
  { value: '', label: 'Any type' },
  { value: 'single', label: 'Single' },
  { value: 'double', label: 'Double' },
  { value: 'quad', label: 'Quad' },
]

const roomColumns = [
  col.accessor((row) => row.hostel_name ?? row.hostel ?? '—', {
    id: 'hostel',
    header: 'Hostel',
  }),
  col.accessor((row) => row.room_number ?? row.number ?? '—', {
    id: 'room_number',
    header: 'Room No.',
  }),
  col.accessor((row) => row.room_type ?? row.type ?? '—', {
    id: 'room_type',
    header: 'Type',
  }),
  col.accessor((row) => row.capacity ?? '—', {
    id: 'capacity',
    header: 'Capacity',
  }),
  col.accessor((row) => row.available_beds ?? row.available_spaces ?? '—', {
    id: 'available',
    header: 'Available Beds',
  }),
]

export default function Hostel() {
  useTitle('Hostel')

  const { data: allocation, isLoading: loadingAllocation, error: allocationError } = useMyHostelAllocation()
  const { data: rooms = [], isLoading: loadingRooms } = useAvailableRooms()
  const { data: sessions = [], isLoading: loadingSessions } = useSessions()
  const { mutate: applyHostel, isPending: applying } = useApplyHostel()

  const [roomType, setRoomType] = useState('')
  const [semesterId, setSemesterId] = useState('')

  // Flatten sessions → semesters for the select
  const semesters = useMemo(() => {
    const result = []
    for (const session of sessions) {
      for (const sem of session.semesters ?? []) {
        result.push({
          id: sem.id,
          label: `${session.name ?? session.year} — ${sem.name ?? sem.term}`,
        })
      }
    }
    return result
  }, [sessions])

  const hasAllocation = !!allocation && !allocationError
  const noAllocation =
    !loadingAllocation &&
    (!allocation || allocationError?.response?.status === 404)

  const handleApply = () => {
    if (!semesterId) {
      toast.error('Please select a semester.')
      return
    }
    const body = { semester_id: Number(semesterId) }
    if (roomType) body.preferred_room_type = roomType
    applyHostel(body, {
      onSuccess: () => toast.success('Hostel application submitted successfully.'),
      onError: (err) => {
        const msg =
          err?.response?.data?.detail ??
          err?.response?.data?.message ??
          err?.message ??
          'Application failed.'
        toast.error(msg)
      },
    })
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Hostel"
        subtitle="Manage your accommodation allocation and application."
      />

      {/* Current allocation */}
      {loadingAllocation && (
        <Card>
          <CardBody>
            <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded animate-pulse w-1/3 mb-2" />
            <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded animate-pulse w-1/2" />
          </CardBody>
        </Card>
      )}

      {hasAllocation && (
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              Current Allocation
            </h2>
          </CardHeader>
          <CardBody>
            <dl className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                { label: 'Hostel', value: allocation.hostel_name ?? allocation.hostel ?? '—' },
                { label: 'Room Number', value: allocation.room_number ?? allocation.room ?? '—' },
                { label: 'Room Type', value: allocation.room_type ?? allocation.type ?? '—' },
                {
                  label: 'Semester',
                  value:
                    allocation.semester_name ??
                    allocation.semester?.name ??
                    allocation.semester_id ??
                    '—',
                },
              ].map(({ label, value }) => (
                <div key={label}>
                  <dt className="text-xs text-slate-500 dark:text-slate-400">{label}</dt>
                  <dd className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100 capitalize">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </CardBody>
        </Card>
      )}

      {/* Apply section */}
      {noAllocation && (
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              Apply for Accommodation
            </h2>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
              <Select
                label="Semester"
                value={semesterId}
                onChange={(e) => setSemesterId(e.target.value)}
                disabled={loadingSessions}
              >
                <option value="">Select semester…</option>
                {semesters.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </Select>

              <Select
                label="Preferred Room Type"
                value={roomType}
                onChange={(e) => setRoomType(e.target.value)}
              >
                {ROOM_TYPES.map((rt) => (
                  <option key={rt.value} value={rt.value}>
                    {rt.label}
                  </option>
                ))}
              </Select>

              <Button variant="primary" loading={applying} onClick={handleApply}>
                Apply
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Available rooms */}
      <div>
        <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3">
          Available Rooms
        </h2>
        <Table
          columns={roomColumns}
          data={rooms}
          isLoading={loadingRooms}
          emptyMessage="No available rooms at the moment."
        />
      </div>
    </div>
  )
}
