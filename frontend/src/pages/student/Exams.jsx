import { useMemo } from 'react'
import { createColumnHelper } from '@tanstack/react-table'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table from '../../components/ui/Table'
import { useExamSlots } from '../../features/exams/queries'

const col = createColumnHelper()

function formatDate(dateStr) {
  if (!dateStr) return '—'
  try {
    return new Date(dateStr).toLocaleDateString('en-GB', {
      weekday: 'short',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

function formatTime(timeStr) {
  if (!timeStr) return '—'
  try {
    const [h, m] = timeStr.split(':')
    const date = new Date()
    date.setHours(Number(h), Number(m))
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })
  } catch {
    return timeStr
  }
}

const columns = [
  col.accessor(
    (row) =>
      row.section?.course?.code ??
      row.course_code ??
      row.section?.course?.title ??
      String(row.section_id ?? '—'),
    {
      id: 'course',
      header: 'Course',
    }
  ),
  col.display({
    id: 'date',
    header: 'Date',
    cell: ({ row }) => formatDate(row.original.date),
  }),
  col.display({
    id: 'start_time',
    header: 'Start Time',
    cell: ({ row }) => formatTime(row.original.start_time),
  }),
  col.display({
    id: 'duration',
    header: 'Duration',
    cell: ({ row }) => {
      const mins = row.original.duration_minutes
      if (!mins) return '—'
      const h = Math.floor(mins / 60)
      const m = mins % 60
      if (h && m) return `${h}h ${m}min`
      if (h) return `${h}h`
      return `${m}min`
    },
  }),
  col.accessor((row) => row.venue ?? '—', {
    id: 'venue',
    header: 'Venue',
  }),
]

export default function Exams() {
  useTitle('Exam Timetable')

  const { data: rawSlots = [], isLoading } = useExamSlots()

  const slots = useMemo(
    () =>
      [...rawSlots].sort((a, b) => {
        const da = new Date(`${a.date}T${a.start_time ?? '00:00'}`)
        const db = new Date(`${b.date}T${b.start_time ?? '00:00'}`)
        return da - db
      }),
    [rawSlots]
  )

  return (
    <div>
      <PageHeader
        title="Exam Timetable"
        subtitle="Your scheduled examination slots for this semester."
      />

      <Table
        columns={columns}
        data={slots}
        isLoading={isLoading}
        emptyMessage="No exams scheduled."
      />
    </div>
  )
}
