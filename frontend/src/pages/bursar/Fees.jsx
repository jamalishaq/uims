import { useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { createColumnHelper } from '@tanstack/react-table'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody } from '../../components/ui/Card'
import Table from '../../components/ui/Table'
import Modal from '../../components/ui/Modal'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import { useFeeSchedule, useCreateFeeSchedule } from '../../features/fees/queries'
import { useSessions, usePrograms } from '../../features/academic/queries'

const FEE_TYPES = [
  { value: 'tuition',           label: 'Tuition' },
  { value: 'acceptance',        label: 'Acceptance' },
  { value: 'application',       label: 'Application' },
  { value: 'accommodation',     label: 'Accommodation' },
  { value: 'library',           label: 'Library' },
  { value: 'department',        label: 'Department' },
  { value: 'exam',              label: 'Exam' },
  { value: 'late_registration', label: 'Late Registration' },
]

const schema = z.object({
  semester_id: z.string().min(1, 'Semester is required'),
  program_id:  z.string().optional(),
  fee_type:    z.string().min(1, 'Fee type is required'),
  amount:      z.coerce.number({ invalid_type_error: 'Must be a number' }).positive('Amount must be positive'),
})

const col = createColumnHelper()

function flattenSemesters(sessions = []) {
  return sessions.flatMap((s) =>
    (s.semesters ?? []).map((sem) => ({
      id:    String(sem.id),
      label: `${s.name} — ${sem.name}`,
    }))
  )
}

export default function BursarFees() {
  useTitle('Fee Schedules')

  const [modalOpen, setModalOpen] = useState(false)
  const [selectedSemester, setSelectedSemester] = useState('')

  const { data: sessions = [], isLoading: sessionsLoading } = useSessions()
  const { data: programs = [] }                              = usePrograms()
  const semesters = useMemo(() => flattenSemesters(sessions), [sessions])

  const scheduleParams = selectedSemester ? { semester_id: selectedSemester } : null
  const { data: schedule = [], isLoading: scheduleLoading } = useFeeSchedule(scheduleParams)

  const { mutate: createSchedule, isPending: creating } = useCreateFeeSchedule()

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      semester_id: '',
      program_id:  '',
      fee_type:    '',
      amount:      '',
    },
  })

  const openModal = () => {
    reset({ semester_id: selectedSemester, program_id: '', fee_type: '', amount: '' })
    setModalOpen(true)
  }

  const onSubmit = (values) => {
    const payload = {
      semester_id: Number(values.semester_id),
      fee_type:    values.fee_type,
      amount:      values.amount,
    }
    if (values.program_id) payload.program_id = Number(values.program_id)

    createSchedule(payload, {
      onSuccess: () => {
        toast.success('Fee schedule created.')
        setModalOpen(false)
        reset()
      },
      onError: (err) => {
        const msg = err?.response?.data?.detail || err?.response?.data?.message || err?.message || 'Failed to create schedule.'
        toast.error(msg)
      },
    })
  }

  const columns = useMemo(
    () => [
      col.accessor('fee_type', {
        header: 'Fee Type',
        cell: (info) => {
          const val = info.getValue()
          const found = FEE_TYPES.find((f) => f.value === val)
          return found ? found.label : (val ?? '—')
        },
      }),
      col.accessor(
        (row) => {
          if (!row.program_id && !row.program) return 'All Programs'
          const prog = programs.find((p) => p.id === (row.program_id ?? row.program))
          return prog?.name ?? row.program_name ?? String(row.program_id ?? '—')
        },
        { id: 'program', header: 'Program' }
      ),
      col.accessor('amount', {
        header: 'Amount',
        cell: (info) => {
          const v = info.getValue()
          if (v == null) return '—'
          return Number(v).toLocaleString('en-NG', { style: 'currency', currency: 'NGN', minimumFractionDigits: 2 })
        },
      }),
    ],
    [programs]
  )

  const configuredCount = schedule.length

  return (
    <div>
      <PageHeader
        title="Fee Schedules"
        subtitle="Configure fee amounts per semester and program."
        action={
          <Button onClick={openModal}>Add Fee Schedule</Button>
        }
      />

      {/* Summary cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardBody className="py-5">
            <p className="text-xs text-slate-500 dark:text-slate-400">Semester</p>
            <p className="mt-1 text-base font-semibold text-slate-900 dark:text-slate-100">
              {selectedSemester
                ? (semesters.find((s) => s.id === selectedSemester)?.label ?? '—')
                : 'All semesters'}
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-5">
            <p className="text-xs text-slate-500 dark:text-slate-400">Fee Types Configured</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">
              {scheduleLoading ? '…' : configuredCount}
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-5">
            <p className="text-xs text-slate-500 dark:text-slate-400">Total Schedules</p>
            <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">
              {scheduleLoading ? '…' : schedule.length}
            </p>
          </CardBody>
        </Card>
      </div>

      {/* Semester filter */}
      <div className="mb-4 max-w-xs">
        <Select
          label="Filter by Semester"
          value={selectedSemester}
          onChange={(e) => setSelectedSemester(e.target.value)}
          disabled={sessionsLoading}
        >
          <option value="">All semesters</option>
          {semesters.map((sem) => (
            <option key={sem.id} value={sem.id}>{sem.label}</option>
          ))}
        </Select>
      </div>

      <Table
        columns={columns}
        data={schedule}
        isLoading={scheduleLoading}
        emptyMessage="No fee schedules configured for this semester."
      />

      {/* Add schedule modal */}
      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title="Add Fee Schedule">
        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <Controller
            name="semester_id"
            control={control}
            render={({ field }) => (
              <Select label="Semester" error={errors.semester_id?.message} {...field}>
                <option value="">Select semester</option>
                {semesters.map((sem) => (
                  <option key={sem.id} value={sem.id}>{sem.label}</option>
                ))}
              </Select>
            )}
          />

          <Controller
            name="program_id"
            control={control}
            render={({ field }) => (
              <Select label="Program (leave blank for all programs)" error={errors.program_id?.message} {...field}>
                <option value="">All programs</option>
                {programs.map((p) => (
                  <option key={p.id} value={String(p.id)}>{p.name}</option>
                ))}
              </Select>
            )}
          />

          <Controller
            name="fee_type"
            control={control}
            render={({ field }) => (
              <Select label="Fee Type" error={errors.fee_type?.message} {...field}>
                <option value="">Select fee type</option>
                {FEE_TYPES.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </Select>
            )}
          />

          <Input
            label="Amount (NGN)"
            type="number"
            min="0"
            step="0.01"
            placeholder="e.g. 150000"
            error={errors.amount?.message}
            {...register('amount')}
          />

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="secondary" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" loading={creating}>
              Create Schedule
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
