import { useState } from 'react'
import toast from 'react-hot-toast'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardHeader, CardBody } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Table, { createColumnHelper } from '../../components/ui/Table'
import Modal from '../../components/ui/Modal'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import { useDepartments } from '../../features/academic/queries'
import { useSessions } from '../../features/academic/queries'
import { useCourses, useAddCourse, useSections, useAddSection } from '../../features/courses/queries'

const COURSE_TYPES = ['core', 'elective', 'general']

// ─── Courses Tab ──────────────────────────────────────────────────────────────

const courseCol = createColumnHelper()
const courseColumns = [
  courseCol.accessor('code', { header: 'Code' }),
  courseCol.accessor('title', { header: 'Title' }),
  courseCol.accessor('credit_hours', { header: 'Credit Hours' }),
  courseCol.accessor('course_type', {
    header: 'Type',
    cell: (i) => {
      const v = i.getValue()
      return v ? v.charAt(0).toUpperCase() + v.slice(1) : '—'
    },
  }),
  courseCol.accessor('department_name', {
    header: 'Department',
    cell: (i) => i.getValue() ?? '—',
  }),
]

function CourseModal({ open, onClose, departments }) {
  const [form, setForm] = useState({
    code: '',
    title: '',
    credit_hours: '',
    course_type: 'core',
    department_id: '',
    description: '',
  })
  const { mutate, isPending } = useAddCourse()

  function handleSubmit(e) {
    e.preventDefault()
    mutate(
      { ...form, credit_hours: Number(form.credit_hours), department_id: Number(form.department_id) },
      {
        onSuccess: () => {
          toast.success('Course created')
          setForm({ code: '', title: '', credit_hours: '', course_type: 'core', department_id: '', description: '' })
          onClose()
        },
        onError: (err) => toast.error(err?.response?.data?.detail || err?.message),
      },
    )
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Course" className="max-w-lg">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Course Code"
            placeholder="e.g. CSC 201"
            value={form.code}
            onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
            required
          />
          <Input
            label="Credit Hours"
            type="number"
            min={1}
            max={12}
            value={form.credit_hours}
            onChange={(e) => setForm((f) => ({ ...f, credit_hours: e.target.value }))}
            required
          />
        </div>
        <Input
          label="Title"
          placeholder="e.g. Data Structures and Algorithms"
          value={form.title}
          onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
          required
        />
        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Course Type"
            value={form.course_type}
            onChange={(e) => setForm((f) => ({ ...f, course_type: e.target.value }))}
          >
            {COURSE_TYPES.map((t) => (
              <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>
            ))}
          </Select>
          <Select
            label="Department"
            value={form.department_id}
            onChange={(e) => setForm((f) => ({ ...f, department_id: e.target.value }))}
            required
          >
            <option value="">Select…</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Description</label>
          <textarea
            rows={3}
            placeholder="Optional course description"
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            className="w-full rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:border-indigo-500 focus:ring-indigo-500/20 resize-none transition-colors"
          />
        </div>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={isPending}>Create</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Sections Tab ─────────────────────────────────────────────────────────────

const sectionCol = createColumnHelper()
const sectionColumns = [
  sectionCol.accessor('course_code', { header: 'Course', cell: (i) => i.getValue() ?? '—' }),
  sectionCol.accessor('semester_name', { header: 'Semester', cell: (i) => i.getValue() ?? '—' }),
  sectionCol.accessor('lecturer_name', { header: 'Lecturer', cell: (i) => i.getValue() ?? '—' }),
  sectionCol.accessor('schedule', { header: 'Schedule', cell: (i) => i.getValue() ?? '—' }),
  sectionCol.accessor('venue', { header: 'Venue', cell: (i) => i.getValue() ?? '—' }),
  sectionCol.accessor('max_enrollment', { header: 'Max Enrollment' }),
]

function SectionModal({ open, onClose, courses, sessions }) {
  const [form, setForm] = useState({
    course_id: '',
    semester_id: '',
    lecturer_id: '',
    max_enrollment: '',
    venue: '',
    schedule: '',
  })
  const { mutate, isPending } = useAddSection()

  // Flatten semesters from all sessions
  const semesters = sessions.flatMap((s) =>
    (s.semesters ?? []).map((sem) => ({
      ...sem,
      label: `${s.name} — ${sem.name.charAt(0).toUpperCase() + sem.name.slice(1)}`,
    })),
  )

  function handleSubmit(e) {
    e.preventDefault()
    mutate(
      {
        ...form,
        course_id: Number(form.course_id),
        semester_id: Number(form.semester_id),
        lecturer_id: form.lecturer_id ? Number(form.lecturer_id) : undefined,
        max_enrollment: form.max_enrollment ? Number(form.max_enrollment) : undefined,
      },
      {
        onSuccess: () => {
          toast.success('Section created')
          setForm({ course_id: '', semester_id: '', lecturer_id: '', max_enrollment: '', venue: '', schedule: '' })
          onClose()
        },
        onError: (err) => toast.error(err?.response?.data?.detail || err?.message),
      },
    )
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Section" className="max-w-lg">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Select
          label="Course"
          value={form.course_id}
          onChange={(e) => setForm((f) => ({ ...f, course_id: e.target.value }))}
          required
        >
          <option value="">Select course…</option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>{c.code} — {c.title}</option>
          ))}
        </Select>
        <Select
          label="Semester"
          value={form.semester_id}
          onChange={(e) => setForm((f) => ({ ...f, semester_id: e.target.value }))}
          required
        >
          <option value="">Select semester…</option>
          {semesters.map((sem) => (
            <option key={sem.id} value={sem.id}>{sem.label}</option>
          ))}
        </Select>
        <Input
          label="Lecturer ID"
          type="number"
          min={1}
          placeholder="User ID of lecturer"
          value={form.lecturer_id}
          onChange={(e) => setForm((f) => ({ ...f, lecturer_id: e.target.value }))}
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Max Enrollment"
            type="number"
            min={1}
            value={form.max_enrollment}
            onChange={(e) => setForm((f) => ({ ...f, max_enrollment: e.target.value }))}
          />
          <Input
            label="Venue"
            placeholder="e.g. LT 1"
            value={form.venue}
            onChange={(e) => setForm((f) => ({ ...f, venue: e.target.value }))}
          />
        </div>
        <Input
          label="Schedule"
          placeholder="e.g. Mon/Wed 10:00–12:00"
          value={form.schedule}
          onChange={(e) => setForm((f) => ({ ...f, schedule: e.target.value }))}
        />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={isPending}>Create</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

const TABS = ['Courses', 'Sections']

export default function Courses() {
  useTitle('Courses')
  const [activeTab, setActiveTab] = useState('Courses')

  // Shared data
  const { data: departments = [] } = useDepartments()
  const { data: sessions = [] } = useSessions()
  const { data: allCourses = [] } = useCourses()

  // Courses tab state
  const [deptFilter, setDeptFilter] = useState('')
  const courseParams = deptFilter ? { department_id: deptFilter } : undefined
  const { data: courses = [], isLoading: loadingCourses } = useCourses(courseParams)
  const [courseModalOpen, setCourseModalOpen] = useState(false)

  // Sections tab state
  const [semesterFilter, setSemesterFilter] = useState('')
  const sectionParams = semesterFilter ? { semester_id: semesterFilter } : undefined
  const { data: sections = [], isLoading: loadingSections } = useSections(sectionParams)
  const [sectionModalOpen, setSectionModalOpen] = useState(false)

  // Flatten semesters for filter dropdown
  const allSemesters = sessions.flatMap((s) =>
    (s.semesters ?? []).map((sem) => ({
      ...sem,
      label: `${s.name} — ${sem.name.charAt(0).toUpperCase() + sem.name.slice(1)}`,
    })),
  )

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Courses" subtitle="Manage courses and class sections" />

      {/* Tabs */}
      <div className="flex gap-1 border-b border-slate-200 dark:border-slate-700">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab
                ? 'border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400'
                : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Courses Tab */}
      {activeTab === 'Courses' && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">All Courses</h2>
              <div className="flex items-center gap-3">
                <select
                  className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  value={deptFilter}
                  onChange={(e) => setDeptFilter(e.target.value)}
                >
                  <option value="">All Departments</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
                <Button size="sm" onClick={() => setCourseModalOpen(true)}>+ Add Course</Button>
              </div>
            </div>
          </CardHeader>
          <CardBody className="p-0">
            <Table
              columns={courseColumns}
              data={courses}
              isLoading={loadingCourses}
              emptyMessage="No courses found"
            />
          </CardBody>
        </Card>
      )}

      {/* Sections Tab */}
      {activeTab === 'Sections' && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Class Sections</h2>
              <div className="flex items-center gap-3">
                <select
                  className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  value={semesterFilter}
                  onChange={(e) => setSemesterFilter(e.target.value)}
                >
                  <option value="">All Semesters</option>
                  {allSemesters.map((sem) => (
                    <option key={sem.id} value={sem.id}>{sem.label}</option>
                  ))}
                </select>
                <Button size="sm" onClick={() => setSectionModalOpen(true)}>+ Add Section</Button>
              </div>
            </div>
          </CardHeader>
          <CardBody className="p-0">
            <Table
              columns={sectionColumns}
              data={sections}
              isLoading={loadingSections}
              emptyMessage="No sections found"
            />
          </CardBody>
        </Card>
      )}

      <CourseModal
        open={courseModalOpen}
        onClose={() => setCourseModalOpen(false)}
        departments={departments}
      />
      <SectionModal
        open={sectionModalOpen}
        onClose={() => setSectionModalOpen(false)}
        courses={allCourses}
        sessions={sessions}
      />
    </div>
  )
}
