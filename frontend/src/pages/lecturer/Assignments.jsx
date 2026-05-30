import { useMemo, useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import toast from 'react-hot-toast'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Table, { createColumnHelper } from '../../components/ui/Table'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import Input from '../../components/ui/Input'
import { useSections } from '../../features/courses/queries'
import {
  useAssignments,
  useAddAssignment,
  useSubmissions,
  useGradeAssignment,
} from '../../features/assignments/queries'

const asgCol = createColumnHelper()
const subCol = createColumnHelper()

export default function Assignments() {
  useTitle('Assignments')
  const { sub: user_id } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const paramSection = searchParams.get('section')

  const [sectionId, setSectionId] = useState(paramSection ?? '')
  const [createOpen, setCreateOpen] = useState(false)
  const [submissionsOpen, setSubmissionsOpen] = useState(false)
  const [selectedAssignment, setSelectedAssignment] = useState(null)

  // Create assignment form state
  const [form, setForm] = useState({
    title: '',
    description: '',
    due_date: '',
    max_score: '',
  })

  // Per-row grade state: { [submissionId]: { score, feedback } }
  const [gradeInputs, setGradeInputs] = useState({})

  const { data: sections = [] } = useSections(user_id ? { lecturer_id: user_id } : undefined)
  const { data: assignments = [], isLoading: asgLoading } = useAssignments(
    sectionId ? { section_id: sectionId } : undefined,
  )
  const { data: submissions = [], isLoading: subLoading } = useSubmissions(
    selectedAssignment?.id ?? null,
  )
  const { mutate: addAssignment, isPending: adding } = useAddAssignment()
  const { mutate: gradeAssignment, isPending: grading } = useGradeAssignment()

  useEffect(() => {
    if (paramSection && paramSection !== sectionId) setSectionId(paramSection)
  }, [paramSection]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleSectionChange(e) {
    const val = e.target.value
    setSectionId(val)
    if (val) setSearchParams({ section: val })
    else setSearchParams({})
  }

  function handleFormChange(e) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }))
  }

  function handleCreate() {
    if (!form.title || !form.due_date) {
      toast.error('Title and due date are required.')
      return
    }
    addAssignment(
      { ...form, section_id: sectionId, max_score: Number(form.max_score) || 100 },
      {
        onSuccess: () => {
          toast.success('Assignment created.')
          setCreateOpen(false)
          setForm({ title: '', description: '', due_date: '', max_score: '' })
        },
        onError: (err) => {
          toast.error(err?.response?.data?.detail || err?.message || 'Failed to create assignment.')
        },
      },
    )
  }

  function openSubmissions(assignment) {
    setSelectedAssignment(assignment)
    setGradeInputs({})
    setSubmissionsOpen(true)
  }

  function handleGradeChange(subId, field, value) {
    setGradeInputs((prev) => ({
      ...prev,
      [subId]: { ...prev[subId], [field]: value },
    }))
  }

  function handleGradeSubmit(sub) {
    const inputs = gradeInputs[sub.id] ?? {}
    gradeAssignment(
      {
        id: selectedAssignment.id,
        submissionId: sub.id,
        score: Number(inputs.score ?? sub.score ?? 0),
        feedback: inputs.feedback ?? sub.feedback ?? '',
      },
      {
        onSuccess: () => toast.success(`Graded ${sub.student_name ?? 'submission'}.`),
        onError: (err) => {
          toast.error(err?.response?.data?.detail || err?.message || 'Failed to save grade.')
        },
      },
    )
  }

  const assignmentColumns = useMemo(
    () => [
      asgCol.accessor('title', { header: 'Title' }),
      asgCol.accessor('due_date', {
        header: 'Due Date',
        cell: (info) => {
          const v = info.getValue()
          return v ? new Date(v).toLocaleString() : '—'
        },
      }),
      asgCol.accessor('submissions_count', {
        header: 'Submissions',
        cell: (info) => (
          <span className="font-medium text-indigo-600 dark:text-indigo-400">
            {info.getValue() ?? 0}
          </span>
        ),
      }),
      asgCol.accessor('max_score', { header: 'Max Score' }),
      asgCol.display({
        id: 'actions',
        header: '',
        cell: ({ row }) => (
          <Button size="sm" variant="secondary" onClick={() => openSubmissions(row.original)}>
            View Submissions
          </Button>
        ),
      }),
    ],
    [], // eslint-disable-line react-hooks/exhaustive-deps
  )

  const submissionColumns = useMemo(
    () => [
      subCol.accessor('student_name', { header: 'Student' }),
      subCol.accessor('matric_number', { header: 'Matric No.' }),
      subCol.accessor('submitted_at', {
        header: 'Submitted',
        cell: (info) => {
          const v = info.getValue()
          return v ? new Date(v).toLocaleString() : '—'
        },
      }),
      subCol.accessor('score', {
        header: 'Score',
        cell: ({ row }) => {
          const sub = row.original
          return (
            <input
              type="number"
              min={0}
              max={selectedAssignment?.max_score ?? 100}
              defaultValue={sub.score ?? ''}
              onChange={(e) => handleGradeChange(sub.id, 'score', e.target.value)}
              className="w-20 rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          )
        },
      }),
      subCol.accessor('feedback', {
        header: 'Feedback',
        cell: ({ row }) => {
          const sub = row.original
          return (
            <input
              type="text"
              defaultValue={sub.feedback ?? ''}
              placeholder="Optional feedback"
              onChange={(e) => handleGradeChange(sub.id, 'feedback', e.target.value)}
              className="w-40 rounded border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
            />
          )
        },
      }),
      subCol.display({
        id: 'save',
        header: '',
        cell: ({ row }) => (
          <Button
            size="sm"
            loading={grading}
            onClick={() => handleGradeSubmit(row.original)}
          >
            Save
          </Button>
        ),
      }),
    ],
    [selectedAssignment, grading], // eslint-disable-line react-hooks/exhaustive-deps
  )

  return (
    <div>
      <PageHeader
        title="Assignments"
        subtitle="Create and manage assignments for your sections."
        action={
          sectionId && (
            <Button onClick={() => setCreateOpen(true)}>+ Create Assignment</Button>
          )
        }
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
          columns={assignmentColumns}
          data={assignments}
          isLoading={asgLoading}
          emptyMessage="No assignments yet for this section."
        />
      ) : (
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Select a section above to view assignments.
        </p>
      )}

      {/* Create Assignment Modal */}
      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create Assignment"
      >
        <div className="space-y-4">
          <Input
            label="Title"
            name="title"
            value={form.title}
            onChange={handleFormChange}
            placeholder="Assignment title"
          />
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
              Description
            </label>
            <textarea
              name="description"
              value={form.description}
              onChange={handleFormChange}
              rows={3}
              placeholder="Assignment instructions (optional)"
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 resize-none"
            />
          </div>
          <Input
            label="Due Date & Time"
            name="due_date"
            type="datetime-local"
            value={form.due_date}
            onChange={handleFormChange}
          />
          <Input
            label="Max Score"
            name="max_score"
            type="number"
            min={1}
            value={form.max_score}
            onChange={handleFormChange}
            placeholder="100"
          />
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button loading={adding} onClick={handleCreate}>
              Create
            </Button>
          </div>
        </div>
      </Modal>

      {/* Submissions Modal */}
      <Modal
        open={submissionsOpen}
        onClose={() => setSubmissionsOpen(false)}
        title={`Submissions — ${selectedAssignment?.title ?? ''}`}
        className="max-w-4xl"
      >
        <Table
          columns={submissionColumns}
          data={submissions}
          isLoading={subLoading}
          emptyMessage="No submissions yet for this assignment."
        />
      </Modal>
    </div>
  )
}
