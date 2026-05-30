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
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import Badge from '../../components/ui/Badge'
import { useGeneratePayments } from '../../features/fees/queries'
import { useFeeCollection } from '../../features/reports/queries'
import { useSessions } from '../../features/academic/queries'

const generateSchema = z.object({
  student_id:  z.string().min(1, 'Student ID is required'),
  semester_id: z.string().min(1, 'Semester is required'),
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

function fmt(val) {
  if (val == null || val === '') return '—'
  return Number(val).toLocaleString('en-NG', { style: 'currency', currency: 'NGN', minimumFractionDigits: 2 })
}

function statusColor(status) {
  if (!status) return 'default'
  const s = status.toLowerCase()
  if (s === 'paid' || s === 'cleared') return 'success'
  if (s === 'partial') return 'warning'
  if (s === 'overdue') return 'danger'
  return 'default'
}

const summaryColDef = [
  col.accessor('fee_type', { header: 'Fee Type' }),
  col.accessor('total_due', { header: 'Total Due', cell: (i) => fmt(i.getValue()) }),
  col.accessor('total_collected', { header: 'Collected', cell: (i) => fmt(i.getValue()) }),
  col.accessor('outstanding', { header: 'Outstanding', cell: (i) => fmt(i.getValue()) }),
]

const generatedColDef = [
  col.accessor('id', { header: 'Payment ID' }),
  col.accessor((r) => r.student?.name ?? r.student_name ?? String(r.student_id ?? '—'), { id: 'student', header: 'Student' }),
  col.accessor('fee_type', { header: 'Fee Type' }),
  col.accessor('amount', { header: 'Amount', cell: (i) => fmt(i.getValue()) }),
  col.display({
    id: 'status',
    header: 'Status',
    cell: ({ row }) => {
      const s = row.original.status ?? 'Pending'
      return <Badge color={statusColor(s)}>{s}</Badge>
    },
  }),
]

export default function BursarPayments() {
  useTitle('Payments')

  const [activeTab, setActiveTab]         = useState('summary')
  const [selectedSemester, setSelectedSemester] = useState('')
  const [generatedPayments, setGeneratedPayments] = useState([])

  const { data: sessions = [], isLoading: sessionsLoading } = useSessions()
  const semesters = useMemo(() => flattenSemesters(sessions), [sessions])

  const reportParams = selectedSemester ? { semester_id: selectedSemester } : null
  const { data: report, isLoading: reportLoading } = useFeeCollection(reportParams)

  // Normalise API response to an array of rows for the breakdown table
  const breakdownRows = useMemo(() => {
    if (!report) return []
    // API might return { rows: [...] } or an array directly
    if (Array.isArray(report)) return report
    if (Array.isArray(report.rows)) return report.rows
    if (Array.isArray(report.breakdown)) return report.breakdown
    return []
  }, [report])

  // Top-level summary from report
  const totalDue       = report?.total_due       ?? report?.summary?.total_due       ?? null
  const totalCollected = report?.total_collected ?? report?.summary?.total_collected ?? null
  const outstanding    = report?.outstanding     ?? report?.summary?.outstanding     ?? null

  const { mutate: generate, isPending: generating } = useGeneratePayments()

  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(generateSchema),
    defaultValues: { student_id: '', semester_id: '' },
  })

  const onGenerate = (values) => {
    generate(
      { student_id: values.student_id, semester_id: values.semester_id },
      {
        onSuccess: (data) => {
          const rows = Array.isArray(data) ? data : data?.payments ?? []
          setGeneratedPayments(rows)
          toast.success(`${rows.length} payment record(s) generated.`)
        },
        onError: (err) => {
          const msg = err?.response?.data?.detail || err?.response?.data?.message || err?.message || 'Failed to generate payments.'
          toast.error(msg)
        },
      }
    )
  }

  const tabs = ['summary', 'generate']

  return (
    <div>
      <PageHeader title="Payments" subtitle="View fee collection reports and generate student payment records." />

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 border-b border-slate-200 dark:border-slate-700">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
                : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
            }`}
          >
            {tab === 'summary' ? 'Summary' : 'Generate Payments'}
          </button>
        ))}
      </div>

      {activeTab === 'summary' && (
        <div>
          {/* Semester selector */}
          <div className="mb-5 max-w-xs">
            <Select
              label="Semester"
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

          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            {[
              { label: 'Total Due',       value: totalDue },
              { label: 'Total Collected', value: totalCollected },
              { label: 'Outstanding',     value: outstanding },
            ].map(({ label, value }) => (
              <Card key={label}>
                <CardBody className="py-5">
                  <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
                  <p className="mt-1 text-xl font-semibold text-slate-900 dark:text-slate-100">
                    {reportLoading ? '…' : fmt(value)}
                  </p>
                </CardBody>
              </Card>
            ))}
          </div>

          {/* Breakdown table */}
          <Table
            columns={summaryColDef}
            data={breakdownRows}
            isLoading={reportLoading}
            emptyMessage="No collection data for this semester."
          />
        </div>
      )}

      {activeTab === 'generate' && (
        <div className="max-w-lg">
          <Card className="mb-6">
            <CardBody>
              <p className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-4">
                Generate payment records for a student and semester
              </p>
              <form onSubmit={handleSubmit(onGenerate)} className="flex flex-col gap-4">
                <Input
                  label="Student ID"
                  placeholder="Enter student ID"
                  error={errors.student_id?.message}
                  {...register('student_id')}
                />

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

                <div className="flex justify-end">
                  <Button type="submit" loading={generating}>
                    Generate Payments
                  </Button>
                </div>
              </form>
            </CardBody>
          </Card>

          {generatedPayments.length > 0 && (
            <div>
              <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-3">
                Generated {generatedPayments.length} payment record(s)
              </p>
              <Table
                columns={generatedColDef}
                data={generatedPayments}
                emptyMessage="No payments generated."
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
