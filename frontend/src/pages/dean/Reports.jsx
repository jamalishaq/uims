import { useMemo } from 'react'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardHeader, CardBody } from '../../components/ui/Card'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { useCgpaDistribution, usePassFailRates } from '../../features/reports/queries'

// ── colour helpers ────────────────────────────────────────────────────────────
const INDIGO = '#4f46e5'
const GREEN  = '#10b981'
const AMBER  = '#f59e0b'
const RED    = '#ef4444'

function passRateColor(rate) {
  if (rate >= 70) return GREEN
  if (rate >= 50) return AMBER
  return RED
}

// ── custom tooltip for pass/fail chart ───────────────────────────────────────
function PassFailTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const rate = payload[0].value
  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-xs shadow">
      <p className="font-medium text-slate-900 dark:text-slate-100 mb-1">{label}</p>
      <p className="text-slate-600 dark:text-slate-300">Pass rate: {rate.toFixed(1)}%</p>
    </div>
  )
}

// ── summary stat card ─────────────────────────────────────────────────────────
function StatCard({ label, value }) {
  return (
    <Card>
      <CardBody className="py-5">
        <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
        <p className="mt-1 text-2xl font-semibold text-slate-900 dark:text-slate-100">{value}</p>
      </CardBody>
    </Card>
  )
}

// ── component ─────────────────────────────────────────────────────────────────
export default function DeanReports() {
  useTitle('Faculty Reports')

  const { data: cgpaData = [], isLoading: cgpaLoading } = useCgpaDistribution()
  const { data: allPassFail = [], isLoading: passFailLoading } = usePassFailRates()

  // Worst 10 courses by pass rate
  const worst10 = useMemo(
    () =>
      [...allPassFail]
        .sort((a, b) => (a.pass_rate ?? 0) - (b.pass_rate ?? 0))
        .slice(0, 10)
        .map((r) => ({
          ...r,
          short_label: r.course_code,
          full_label:  `${r.course_code} — ${r.course_title}`,
        })),
    [allPassFail]
  )

  // Summary stats
  const totalStudents = useMemo(
    () => cgpaData.reduce((sum, r) => sum + (r.count ?? 0), 0),
    [cgpaData]
  )

  const avgPassRate = useMemo(() => {
    if (!allPassFail.length) return null
    const sum = allPassFail.reduce((acc, r) => acc + (r.pass_rate ?? 0), 0)
    return (sum / allPassFail.length).toFixed(1)
  }, [allPassFail])

  const coursesBelowFifty = useMemo(
    () => allPassFail.filter((r) => (r.pass_rate ?? 0) < 50).length,
    [allPassFail]
  )

  return (
    <div className="space-y-6">
      <PageHeader title="Faculty Reports" subtitle="Institutional analytics" />

      {/* Summary stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          label="Total Students"
          value={cgpaLoading ? '…' : totalStudents.toLocaleString()}
        />
        <StatCard
          label="Avg Pass Rate"
          value={passFailLoading ? '…' : avgPassRate != null ? `${avgPassRate}%` : '—'}
        />
        <StatCard
          label="Courses Below 50%"
          value={passFailLoading ? '…' : coursesBelowFifty}
        />
      </div>

      {/* CGPA Distribution chart */}
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            CGPA Distribution
          </h2>
        </CardHeader>
        <CardBody>
          {cgpaLoading ? (
            <div className="h-56 flex items-center justify-center text-sm text-slate-400">
              Loading…
            </div>
          ) : cgpaData.length === 0 ? (
            <div className="h-56 flex items-center justify-center text-sm text-slate-400">
              No data available
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={cgpaData}
                margin={{ top: 4, right: 8, left: 0, bottom: 4 }}
              >
                <XAxis
                  dataKey="range"
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  width={32}
                />
                <Tooltip
                  formatter={(v) => [v, 'Students']}
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 8,
                    border: '1px solid #e2e8f0',
                  }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]} fill={INDIGO} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardBody>
      </Card>

      {/* Pass / Fail rates — worst 10 courses (horizontal bar) */}
      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
            Lowest Pass Rates (top 10 worst courses)
          </h2>
        </CardHeader>
        <CardBody>
          {passFailLoading ? (
            <div className="h-56 flex items-center justify-center text-sm text-slate-400">
              Loading…
            </div>
          ) : worst10.length === 0 ? (
            <div className="h-56 flex items-center justify-center text-sm text-slate-400">
              No data available
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(worst10.length * 38, 200)}>
              <BarChart
                layout="vertical"
                data={worst10}
                margin={{ top: 4, right: 40, left: 8, bottom: 4 }}
              >
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  unit="%"
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="short_label"
                  width={68}
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip content={<PassFailTooltip />} />
                <Bar dataKey="pass_rate" radius={[0, 4, 4, 0]}>
                  {worst10.map((entry, idx) => (
                    <Cell key={idx} fill={passRateColor(entry.pass_rate ?? 0)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardBody>
      </Card>
    </div>
  )
}
