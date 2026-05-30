import { useMemo } from 'react'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardHeader, CardBody } from '../../components/ui/Card'
import Table, { createColumnHelper } from '../../components/ui/Table'
import { useEnrollmentStats, useCgpaDistribution } from '../../features/reports/queries'
import { usePrograms } from '../../features/academic/queries'

// ── column helper for programs table ─────────────────────────────────────────
const col = createColumnHelper()

const programColumns = [
  col.accessor('program_name', { header: 'Program' }),
  col.accessor('level',        { header: 'Level' }),
  col.accessor('student_count',{
    header: 'Students',
    enableSorting: true,
    cell: (info) => (info.getValue() ?? 0).toLocaleString(),
  }),
]

// ── stat card ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, sub }) {
  return (
    <Card>
      <CardBody className="py-5">
        <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
        <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">{value}</p>
        {sub && (
          <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-500">{sub}</p>
        )}
      </CardBody>
    </Card>
  )
}

// ── component ─────────────────────────────────────────────────────────────────
export default function DeanOverview() {
  useTitle('Faculty Overview')

  const { data: programs = [], isLoading: programsLoading } = usePrograms()
  const { data: enrollmentStats = [], isLoading: enrollLoading } = useEnrollmentStats()
  const { data: cgpaData = [], isLoading: cgpaLoading } = useCgpaDistribution()

  // Total students from enrollment stats
  const totalStudents = useMemo(
    () => enrollmentStats.reduce((sum, r) => sum + (r.student_count ?? 0), 0),
    [enrollmentStats]
  )

  // Weighted average CGPA — cgpaData has { range, count } where range is e.g. "3.5-4.0"
  // We use midpoint of each range as proxy
  const averageCgpa = useMemo(() => {
    if (!cgpaData.length) return null
    let weightedSum = 0
    let total = 0
    cgpaData.forEach(({ range, count }) => {
      if (!range || !count) return
      // Parse midpoint: "3.50-4.00" or "3.5-4.0" etc.
      const parts = String(range).split('-')
      if (parts.length === 2) {
        const lo = parseFloat(parts[0])
        const hi = parseFloat(parts[1])
        if (!isNaN(lo) && !isNaN(hi)) {
          weightedSum += ((lo + hi) / 2) * count
          total += count
        }
      }
    })
    return total > 0 ? (weightedSum / total).toFixed(2) : null
  }, [cgpaData])

  // Build program rows with student counts from enrollment stats
  const programRows = useMemo(() => {
    // Build a map: program_name → student_count from enrollment stats
    const countMap = {}
    enrollmentStats.forEach((r) => {
      const key = r.program_name
      countMap[key] = (countMap[key] ?? 0) + (r.student_count ?? 0)
    })

    // If enrollment stats exist, use them to enrich programs list
    if (enrollmentStats.length > 0) {
      // Deduplicate by program_name from enrollment stats
      const seen = new Set()
      return enrollmentStats
        .filter((r) => {
          if (seen.has(r.program_name)) return false
          seen.add(r.program_name)
          return true
        })
        .map((r) => ({
          program_name: r.program_name,
          level: r.level,
          student_count: countMap[r.program_name] ?? 0,
        }))
    }

    // Fallback to programs list without counts
    return programs.map((p) => ({
      program_name: p.name,
      level: p.level ?? '—',
      student_count: 0,
    }))
  }, [enrollmentStats, programs])

  const isLoading = enrollLoading || programsLoading

  return (
    <div className="space-y-6">
      <PageHeader title="Faculty Overview" subtitle="High-level faculty metrics and program enrollment" />

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          label="Total Programs"
          value={programsLoading ? '…' : programs.length}
        />
        <StatCard
          label="Total Students"
          value={enrollLoading ? '…' : totalStudents.toLocaleString()}
          sub="from enrollment stats"
        />
        <StatCard
          label="Average CGPA"
          value={cgpaLoading ? '…' : averageCgpa ?? '—'}
          sub="estimated from distribution"
        />
      </div>

      {/* Programs table */}
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Programs &amp; Enrollment
          </h2>
        </CardHeader>
        <div className="overflow-x-auto">
          <Table
            columns={programColumns}
            data={programRows}
            isLoading={isLoading}
            emptyMessage="No programs found"
          />
        </div>
      </Card>
    </div>
  )
}
