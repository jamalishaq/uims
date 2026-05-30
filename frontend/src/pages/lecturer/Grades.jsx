import { useMemo, useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table, { createColumnHelper } from '../../components/ui/Table'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import { useSections } from '../../features/courses/queries'
import { useSectionGrades, useSubmitGrade } from '../../features/grades/queries'

const col = createColumnHelper()

function letterGrade(total) {
  if (total >= 70) return { letter: 'A', color: 'success' }
  if (total >= 60) return { letter: 'B', color: 'indigo' }
  if (total >= 50) return { letter: 'C', color: 'warning' }
  if (total >= 45) return { letter: 'D', color: 'warning' }
  return { letter: 'F', color: 'danger' }
}

export default function Grades() {
  useTitle('Grades')
  const { sub: user_id } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const paramSection = searchParams.get('section')

  const [sectionId, setSectionId] = useState(paramSection ?? '')
  // Per-row edits: { [enrollmentId]: { ca_score, exam_score } }
  const [edits, setEdits] = useState({})
  // Track which rows have been submitted to show computed result
  const [submitted, setSubmitted] = useState({})

  const { data: sections = [] } = useSections(user_id ? { lecturer_id: user_id } : undefined)
  const { data: enrollments = [], isLoading } = useSectionGrades(sectionId || null)
  const { mutate: submitGrade, isPending } = useSubmitGrade()

  useEffect(() => {
    if (paramSection && paramSection !== sectionId) setSectionId(paramSection)
  }, [paramSection]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleSectionChange(e) {
    const val = e.target.value
    setSectionId(val)
    setEdits({})
    setSubmitted({})
    if (val) setSearchParams({ section: val })
    else setSearchParams({})
  }

  function handleEdit(enrollmentId, field, value) {
    setEdits((prev) => ({
      ...prev,
      [enrollmentId]: { ...prev[enrollmentId], [field]: value },
    }))
  }

  function handleSubmit(enrollment) {
    const row = edits[enrollment.id] ?? {}
    const ca = Number(row.ca_score ?? enrollment.ca_score ?? 0)
    const exam = Number(row.exam_score ?? enrollment.exam_score ?? 0)

    submitGrade(
      { enrollmentId: enrollment.id, ca_score: ca, exam_score: exam },
      {
        onSuccess: (data) => {
          toast.success(`Grade submitted for ${enrollment.student_name}.`)
          setSubmitted((prev) => ({
            ...prev,
            [enrollment.id]: {
              ca,
              exam,
              total: data?.total ?? ca + exam,
              grade: data?.grade ?? letterGrade(ca + exam).letter,
            },
          }))
        },
        onError: (err) => {
          toast.error(err?.response?.data?.detail || err?.message || 'Failed to submit grade.')
        },
      },
    )
  }

  const columns = useMemo(
    () => [
      col.accessor('matric_number', { header: 'Matric No.' }),
      col.accessor('student_name', { header: 'Student Name' }),
      col.accessor('ca_score', {
        header: 'CA Score',
        cell: ({ row }) => {
          const en = row.original
          const val = edits[en.id]?.ca_score ?? en.ca_score ?? ''
          return (
            <input
              type="number"
              min={0}
              max={40}
              value={val}
              onChange={(e) => handleEdit(en.id, 'ca_score', e.target.value)}
              className="w-20 rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          )
        },
      }),
      col.accessor('exam_score', {
        header: 'Exam Score',
        cell: ({ row }) => {
          const en = row.original
          const val = edits[en.id]?.exam_score ?? en.exam_score ?? ''
          return (
            <input
              type="number"
              min={0}
              max={60}
              value={val}
              onChange={(e) => handleEdit(en.id, 'exam_score', e.target.value)}
              className="w-20 rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          )
        },
      }),
      col.display({
        id: 'total',
        header: 'Total',
        cell: ({ row }) => {
          const en = row.original
          const sub = submitted[en.id]
          if (sub) return <span className="font-medium">{sub.total}</span>
          const ca = Number(edits[en.id]?.ca_score ?? en.ca_score ?? 0)
          const exam = Number(edits[en.id]?.exam_score ?? en.exam_score ?? 0)
          const total = ca + exam
          return <span className="text-slate-400 dark:text-slate-500">{total || '—'}</span>
        },
      }),
      col.display({
        id: 'grade',
        header: 'Grade',
        cell: ({ row }) => {
          const en = row.original
          const sub = submitted[en.id]
          if (sub) {
            const { color } = letterGrade(sub.total)
            return (
              <span className="flex items-center gap-2">
                <Badge color={color}>{sub.grade}</Badge>
                <Badge color={sub.total >= 45 ? 'success' : 'danger'}>
                  {sub.total >= 45 ? 'Pass' : 'Fail'}
                </Badge>
              </span>
            )
          }
          return <span className="text-slate-400 dark:text-slate-500">—</span>
        },
      }),
      col.display({
        id: 'action',
        header: '',
        cell: ({ row }) => (
          <Button
            size="sm"
            loading={isPending}
            onClick={() => handleSubmit(row.original)}
          >
            Submit
          </Button>
        ),
      }),
    ],
    [edits, submitted, isPending], // eslint-disable-line react-hooks/exhaustive-deps
  )

  return (
    <div>
      <PageHeader
        title="Grades"
        subtitle="Enter and submit CA and exam scores for enrolled students."
      />

      {/* Section selector */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
          Select Section
        </label>
        <select
          value={sectionId}
          onChange={handleSectionChange}
          className="w-full max-w-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
        >
          <option value="">— Choose a section —</option>
          {sections.map((s) => (
            <option key={s.id} value={s.id}>
              {s.course_code} — {s.course_title} ({s.semester})
            </option>
          ))}
        </select>
      </div>

      {sectionId ? (
        <Table
          columns={columns}
          data={enrollments}
          isLoading={isLoading}
          emptyMessage="No students enrolled in this section."
        />
      ) : (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Select a section above to manage grades.
        </p>
      )}
    </div>
  )
}
