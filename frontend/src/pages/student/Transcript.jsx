import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import PageHeader, { StatTile } from '../../components/PageHeader'
import Badge, { StatusBadge } from '../../components/ui/Badge'
import { ErrorNote, Loading, Note } from '../../components/ui/Feedback'
import EmptyState from '../../components/EmptyState'
import { useAcademicRecord } from '../../features/academicRecords/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'

/**
 * Every attempt ever recorded, grouped by semester.
 *
 * **Every attempt counts and none is replaced.** A course failed and later passed is two lines
 * here and two contributions to the CGPA — the confirmed carry-over rule — so this deliberately
 * does not collapse repeats into a best attempt. A transcript that hid the first try would be
 * showing something the university does not hold.
 *
 * Numbers are rendered as the strings the API sent. They are exact decimals quantized to two
 * places, and parsing them into JavaScript floats to format them would reintroduce the rounding
 * the server went out of its way to avoid.
 */
export default function Transcript() {
  useTitle('Transcript')
  const { scopeId } = useAuth()
  const { data, isLoading, error } = useAcademicRecord(scopeId)

  if (isLoading) return <Loading label="Loading your transcript…" />

  if (error) {
    return (
      <>
        <PageHeader title="Transcript" />
        <EmptyState
          title="No academic record"
          description="A record is created the first time a grade is submitted for you. If you have just registered, there is nothing to show yet — that is normal, not a fault."
        />
      </>
    )
  }

  const bySemester = data.grades.reduce((groups, line) => {
    ;(groups[line.semester_id] ??= []).push(line)
    return groups
  }, {})

  const attempts = data.grades.reduce((counts, line) => {
    counts[line.course_id] = (counts[line.course_id] ?? 0) + 1
    return counts
  }, {})

  return (
    <>
      <PageHeader
        title="Transcript"
        description="Every attempt, in the order it was recorded."
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <StatTile label="CGPA" value={data.cgpa} caption="Two decimals, half up." />
        <StatTile label="Units attempted" value={data.total_units} />
        <StatTile
          label="Standing"
          value={<StatusBadge status={data.standing} />}
          tone={data.standing === 'probation' ? 'danger' : 'success'}
        />
      </div>

      <div className="space-y-6">
        {Object.entries(bySemester).map(([semesterId, lines]) => (
          <Card key={semesterId}>
            <CardHeader
              title={semesterId}
              description={`${lines.length} ${lines.length === 1 ? 'course' : 'courses'}`}
              action={
                data.semester_gpas[semesterId] && (
                  <span className="tabular text-sm text-ink-600 dark:text-ink-400">
                    GPA <strong className="text-ink-900 dark:text-ink-100">
                      {data.semester_gpas[semesterId]}
                    </strong>
                  </span>
                )
              }
            />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-500 dark:bg-ink-800/60 dark:text-ink-400">
                  <tr>
                    <th className="px-5 py-2.5 text-left font-medium">Course</th>
                    <th className="px-5 py-2.5 text-right font-medium">Units</th>
                    <th className="px-5 py-2.5 text-right font-medium">Score</th>
                    <th className="px-5 py-2.5 text-center font-medium">Grade</th>
                    <th className="px-5 py-2.5 text-right font-medium">Points</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.map((line) => (
                    <tr
                      key={`${line.course_id}-${line.semester_id}`}
                      className="border-t border-ink-200 dark:border-ink-800"
                    >
                      <td className="px-5 py-3">
                        <span className="font-mono text-ink-900 dark:text-ink-100">
                          {line.course_id}
                        </span>
                        {attempts[line.course_id] > 1 && (
                          <Badge tone="warning" className="ml-2">
                            Carry-over
                          </Badge>
                        )}
                      </td>
                      <td className="px-5 py-3 text-right">{line.credit_units}</td>
                      <td className="px-5 py-3 text-right">{line.score}</td>
                      <td className="px-5 py-3 text-center">
                        <Badge tone={line.is_pass ? 'success' : 'danger'}>{line.letter}</Badge>
                      </td>
                      <td className="px-5 py-3 text-right">{line.quality_points}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        ))}
      </div>

      {data.corrections.length > 0 && (
        <Card className="mt-6">
          <CardHeader
            title="Corrections"
            description="A corrected grade is appended, never overwritten. The original stays."
          />
          <CardBody className="space-y-3">
            {data.corrections.map((correction, index) => (
              <div
                key={index}
                className="rounded-lg border border-ink-200 px-4 py-3 text-sm dark:border-ink-800"
              >
                <p className="font-mono text-ink-900 dark:text-ink-100">
                  {correction.course_id} · {correction.semester_id}
                </p>
                <p className="mt-1 text-ink-600 dark:text-ink-400">
                  {correction.previous_score} → {correction.corrected_score}
                </p>
                <p className="mt-1 hint">
                  {correction.reason} — authorised by {correction.authorized_by}
                </p>
              </div>
            ))}
          </CardBody>
        </Card>
      )}

      {data.grades.length === 0 && (
        <EmptyState
          title="No grades recorded"
          description="Your record exists but carries no lines yet."
        />
      )}

      <Note tone="info" className="mt-6">
        Every attempt at a course appears here and counts towards the CGPA. Passing a course on a
        second attempt does not remove the first.
      </Note>

      <ErrorNote error={error} className="mt-6" />
    </>
  )
}
