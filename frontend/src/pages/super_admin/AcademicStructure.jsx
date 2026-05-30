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
import {
  useFaculties,
  useAddFaculty,
  useDepartments,
  useAddDepartment,
  usePrograms,
  useAddProgram,
} from '../../features/academic/queries'

// ─── Faculties ───────────────────────────────────────────────────────────────

const facultyCol = createColumnHelper()
const facultyColumns = [
  facultyCol.accessor('name', { header: 'Name' }),
  facultyCol.accessor('code', { header: 'Code' }),
]

function FacultyModal({ open, onClose }) {
  const [form, setForm] = useState({ name: '', code: '' })
  const { mutate, isPending } = useAddFaculty()

  function handleSubmit(e) {
    e.preventDefault()
    mutate(form, {
      onSuccess: () => {
        toast.success('Faculty created')
        setForm({ name: '', code: '' })
        onClose()
      },
      onError: (err) => toast.error(err?.response?.data?.detail || err?.message),
    })
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Faculty">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="Name"
          placeholder="e.g. Faculty of Engineering"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          required
        />
        <Input
          label="Code"
          placeholder="e.g. ENG"
          value={form.code}
          onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
          required
        />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={isPending}>Create</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Departments ──────────────────────────────────────────────────────────────

const deptCol = createColumnHelper()
const deptColumns = [
  deptCol.accessor('name', { header: 'Name' }),
  deptCol.accessor('code', { header: 'Code' }),
]

function DepartmentModal({ open, onClose, faculties, selectedFacultyId }) {
  const [form, setForm] = useState({ name: '', code: '', faculty_id: selectedFacultyId ?? '' })
  const { mutate, isPending } = useAddDepartment()

  // sync pre-fill when selectedFacultyId changes (modal open)
  function handleOpen() {
    setForm({ name: '', code: '', faculty_id: selectedFacultyId ?? '' })
  }

  function handleSubmit(e) {
    e.preventDefault()
    mutate(
      { ...form, faculty_id: Number(form.faculty_id) },
      {
        onSuccess: () => {
          toast.success('Department created')
          setForm({ name: '', code: '', faculty_id: selectedFacultyId ?? '' })
          onClose()
        },
        onError: (err) => toast.error(err?.response?.data?.detail || err?.message),
      },
    )
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Department">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" onFocus={handleOpen}>
        <Select
          label="Faculty"
          value={form.faculty_id}
          onChange={(e) => setForm((f) => ({ ...f, faculty_id: e.target.value }))}
          required
        >
          <option value="">Select faculty…</option>
          {faculties.map((f) => (
            <option key={f.id} value={f.id}>{f.name}</option>
          ))}
        </Select>
        <Input
          label="Name"
          placeholder="e.g. Computer Science"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          required
        />
        <Input
          label="Code"
          placeholder="e.g. CSC"
          value={form.code}
          onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
          required
        />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={isPending}>Create</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Programs ─────────────────────────────────────────────────────────────────

const progCol = createColumnHelper()
const progColumns = [
  progCol.accessor('name', { header: 'Name' }),
  progCol.accessor('code', { header: 'Code' }),
  progCol.accessor('degree_type', { header: 'Degree Type', cell: (i) => i.getValue()?.toUpperCase() }),
  progCol.accessor('duration_years', { header: 'Duration (yrs)' }),
  progCol.accessor('total_credits_required', { header: 'Total Credits' }),
]

const DEGREE_TYPES = ['bsc', 'msc', 'phd', 'pgde']

function ProgramModal({ open, onClose, departments, selectedDeptId }) {
  const [form, setForm] = useState({
    name: '',
    code: '',
    department_id: selectedDeptId ?? '',
    degree_type: 'bsc',
    duration_years: 4,
    total_credits_required: '',
    core_credits_required: '',
    elective_credits_required: '',
  })
  const { mutate, isPending } = useAddProgram()

  function handleSubmit(e) {
    e.preventDefault()
    mutate(
      {
        ...form,
        department_id: Number(form.department_id),
        duration_years: Number(form.duration_years),
        total_credits_required: Number(form.total_credits_required),
        core_credits_required: Number(form.core_credits_required),
        elective_credits_required: Number(form.elective_credits_required),
      },
      {
        onSuccess: () => {
          toast.success('Program created')
          onClose()
        },
        onError: (err) => toast.error(err?.response?.data?.detail || err?.message),
      },
    )
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Program" className="max-w-lg">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Select
          label="Department"
          value={form.department_id}
          onChange={(e) => setForm((f) => ({ ...f, department_id: e.target.value }))}
          required
        >
          <option value="">Select department…</option>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </Select>
        <Input
          label="Name"
          placeholder="e.g. B.Sc. Computer Science"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          required
        />
        <Input
          label="Code"
          placeholder="e.g. BSC-CSC"
          value={form.code}
          onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
          required
        />
        <Select
          label="Degree Type"
          value={form.degree_type}
          onChange={(e) => setForm((f) => ({ ...f, degree_type: e.target.value }))}
        >
          {DEGREE_TYPES.map((t) => (
            <option key={t} value={t}>{t.toUpperCase()}</option>
          ))}
        </Select>
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Duration (years)"
            type="number"
            min={1}
            max={10}
            value={form.duration_years}
            onChange={(e) => setForm((f) => ({ ...f, duration_years: e.target.value }))}
            required
          />
          <Input
            label="Total Credits"
            type="number"
            min={0}
            value={form.total_credits_required}
            onChange={(e) => setForm((f) => ({ ...f, total_credits_required: e.target.value }))}
            required
          />
          <Input
            label="Core Credits"
            type="number"
            min={0}
            value={form.core_credits_required}
            onChange={(e) => setForm((f) => ({ ...f, core_credits_required: e.target.value }))}
            required
          />
          <Input
            label="Elective Credits"
            type="number"
            min={0}
            value={form.elective_credits_required}
            onChange={(e) => setForm((f) => ({ ...f, elective_credits_required: e.target.value }))}
            required
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

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function AcademicStructure() {
  useTitle('Academic Structure')

  // Faculties
  const { data: faculties = [], isLoading: loadingFaculties } = useFaculties()
  const [facultyModalOpen, setFacultyModalOpen] = useState(false)

  // Departments
  const [selectedFacultyId, setSelectedFacultyId] = useState('')
  const deptParams = selectedFacultyId ? { faculty_id: selectedFacultyId } : undefined
  const { data: departments = [], isLoading: loadingDepts } = useDepartments(deptParams)
  const [deptModalOpen, setDeptModalOpen] = useState(false)

  // Programs
  const [selectedDeptId, setSelectedDeptId] = useState('')
  const progParams = selectedDeptId ? { department_id: selectedDeptId } : undefined
  const { data: programs = [], isLoading: loadingProgs } = usePrograms(progParams)
  const [progModalOpen, setProgModalOpen] = useState(false)

  // All departments (unfiltered) for program modal dept selector
  const { data: allDepartments = [] } = useDepartments()

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Academic Structure"
        subtitle="Manage faculties, departments, and programs"
      />

      {/* Faculties */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Faculties</h2>
            <Button size="sm" onClick={() => setFacultyModalOpen(true)}>+ Add Faculty</Button>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <Table columns={facultyColumns} data={faculties} isLoading={loadingFaculties} emptyMessage="No faculties yet" />
        </CardBody>
      </Card>

      {/* Departments */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Departments</h2>
            <div className="flex items-center gap-3">
              <select
                className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                value={selectedFacultyId}
                onChange={(e) => setSelectedFacultyId(e.target.value)}
              >
                <option value="">All Faculties</option>
                {faculties.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
              <Button size="sm" onClick={() => setDeptModalOpen(true)}>+ Add Department</Button>
            </div>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <Table columns={deptColumns} data={departments} isLoading={loadingDepts} emptyMessage="No departments found" />
        </CardBody>
      </Card>

      {/* Programs */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">Programs</h2>
            <div className="flex items-center gap-3">
              <select
                className="rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                value={selectedDeptId}
                onChange={(e) => setSelectedDeptId(e.target.value)}
              >
                <option value="">All Departments</option>
                {allDepartments.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
              <Button size="sm" onClick={() => setProgModalOpen(true)}>+ Add Program</Button>
            </div>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          <Table columns={progColumns} data={programs} isLoading={loadingProgs} emptyMessage="No programs found" />
        </CardBody>
      </Card>

      <FacultyModal open={facultyModalOpen} onClose={() => setFacultyModalOpen(false)} />
      <DepartmentModal
        open={deptModalOpen}
        onClose={() => setDeptModalOpen(false)}
        faculties={faculties}
        selectedFacultyId={selectedFacultyId}
      />
      <ProgramModal
        open={progModalOpen}
        onClose={() => setProgModalOpen(false)}
        departments={allDepartments}
        selectedDeptId={selectedDeptId}
      />
    </div>
  )
}
