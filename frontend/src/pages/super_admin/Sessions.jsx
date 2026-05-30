import { useState } from 'react'
import toast from 'react-hot-toast'
import { ChevronDown, ChevronRight } from 'lucide-react'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardHeader, CardBody } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import Badge from '../../components/ui/Badge'
import { useSessions, useAddSession, useAddSemester } from '../../features/academic/queries'

const SEMESTER_NAMES = ['first', 'second', 'summer']

// ─── Add Session Modal ────────────────────────────────────────────────────────

function SessionModal({ open, onClose }) {
  const [form, setForm] = useState({
    name: '',
    start_date: '',
    end_date: '',
    is_current: false,
  })
  const { mutate, isPending } = useAddSession()

  function handleSubmit(e) {
    e.preventDefault()
    mutate(form, {
      onSuccess: () => {
        toast.success('Session created')
        setForm({ name: '', start_date: '', end_date: '', is_current: false })
        onClose()
      },
      onError: (err) => toast.error(err?.response?.data?.detail || err?.message),
    })
  }

  return (
    <Modal open={open} onClose={onClose} title="Add Academic Session">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Input
          label="Session Name"
          placeholder="e.g. 2024/2025"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          required
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Start Date"
            type="date"
            value={form.start_date}
            onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
            required
          />
          <Input
            label="End Date"
            type="date"
            value={form.end_date}
            onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
            required
          />
        </div>
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            checked={form.is_current}
            onChange={(e) => setForm((f) => ({ ...f, is_current: e.target.checked }))}
          />
          <span className="text-sm text-slate-700 dark:text-slate-300">Mark as current session</span>
        </label>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={isPending}>Create</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Add Semester Modal ───────────────────────────────────────────────────────

function SemesterModal({ open, onClose, sessionId, sessionName }) {
  const [form, setForm] = useState({
    name: 'first',
    start_date: '',
    end_date: '',
    registration_start: '',
    registration_end: '',
    is_current: false,
  })
  const { mutate, isPending } = useAddSemester()

  function handleSubmit(e) {
    e.preventDefault()
    mutate(
      { sessionId, ...form },
      {
        onSuccess: () => {
          toast.success('Semester created')
          setForm({
            name: 'first',
            start_date: '',
            end_date: '',
            registration_start: '',
            registration_end: '',
            is_current: false,
          })
          onClose()
        },
        onError: (err) => toast.error(err?.response?.data?.detail || err?.message),
      },
    )
  }

  return (
    <Modal open={open} onClose={onClose} title={`Add Semester — ${sessionName}`} className="max-w-lg">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Select
          label="Semester"
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        >
          {SEMESTER_NAMES.map((n) => (
            <option key={n} value={n}>{n.charAt(0).toUpperCase() + n.slice(1)} Semester</option>
          ))}
        </Select>
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Start Date"
            type="date"
            value={form.start_date}
            onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))}
            required
          />
          <Input
            label="End Date"
            type="date"
            value={form.end_date}
            onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))}
            required
          />
          <Input
            label="Registration Start"
            type="date"
            value={form.registration_start}
            onChange={(e) => setForm((f) => ({ ...f, registration_start: e.target.value }))}
          />
          <Input
            label="Registration End"
            type="date"
            value={form.registration_end}
            onChange={(e) => setForm((f) => ({ ...f, registration_end: e.target.value }))}
          />
        </div>
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            checked={form.is_current}
            onChange={(e) => setForm((f) => ({ ...f, is_current: e.target.checked }))}
          />
          <span className="text-sm text-slate-700 dark:text-slate-300">Mark as current semester</span>
        </label>
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>Cancel</Button>
          <Button type="submit" loading={isPending}>Create</Button>
        </div>
      </form>
    </Modal>
  )
}

// ─── Session Row ──────────────────────────────────────────────────────────────

function SessionRow({ session }) {
  const [expanded, setExpanded] = useState(false)
  const [semesterModalOpen, setSemesterModalOpen] = useState(false)
  const semesters = session.semesters ?? []

  return (
    <>
      <tr className="border-t border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors duration-150">
        <td className="px-4 py-3">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1.5 text-sm font-medium text-slate-800 dark:text-slate-100 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors"
          >
            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            {session.name}
          </button>
        </td>
        <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">{session.start_date}</td>
        <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">{session.end_date}</td>
        <td className="px-4 py-3">
          {session.is_current ? (
            <Badge color="success">Current</Badge>
          ) : (
            <Badge color="default">Past</Badge>
          )}
        </td>
        <td className="px-4 py-3 text-right">
          <Button
            size="sm"
            variant="secondary"
            onClick={() => setSemesterModalOpen(true)}
          >
            + Semester
          </Button>
        </td>
      </tr>

      {expanded && (
        <tr className="border-t border-slate-100 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-800/30">
          <td colSpan={5} className="px-6 py-3">
            {semesters.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No semesters yet. Click "+ Semester" to add one.</p>
            ) : (
              <div className="rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-slate-100 dark:bg-slate-800">
                    <tr>
                      {['Semester', 'Start', 'End', 'Reg. Start', 'Reg. End', 'Status'].map((h) => (
                        <th key={h} className="px-3 py-2 text-left font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {semesters.map((sem) => (
                      <tr
                        key={sem.id}
                        className="border-t border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/30"
                      >
                        <td className="px-3 py-2 capitalize font-medium text-slate-700 dark:text-slate-300">{sem.name}</td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{sem.start_date}</td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{sem.end_date}</td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{sem.registration_start ?? '—'}</td>
                        <td className="px-3 py-2 text-slate-600 dark:text-slate-400">{sem.registration_end ?? '—'}</td>
                        <td className="px-3 py-2">
                          {sem.is_current ? <Badge color="success">Current</Badge> : <Badge color="default">Past</Badge>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </td>
        </tr>
      )}

      <SemesterModal
        open={semesterModalOpen}
        onClose={() => setSemesterModalOpen(false)}
        sessionId={session.id}
        sessionName={session.name}
      />
    </>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function Sessions() {
  useTitle('Academic Sessions')
  const { data: sessions = [], isLoading } = useSessions()
  const [sessionModalOpen, setSessionModalOpen] = useState(false)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Academic Sessions"
        subtitle="Manage sessions and their semesters"
        action={
          <Button onClick={() => setSessionModalOpen(true)}>+ Add Session</Button>
        }
      />

      <Card>
        <CardBody className="p-0">
          <div className="rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden">
            <table className="w-full text-sm border-collapse">
              <thead className="bg-slate-50 dark:bg-slate-800/60">
                <tr>
                  {['Session', 'Start Date', 'End Date', 'Status', ''].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wide whitespace-nowrap"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading
                  ? Array.from({ length: 4 }).map((_, i) => (
                      <tr key={i} className="border-t border-slate-200 dark:border-slate-700">
                        {Array.from({ length: 5 }).map((__, j) => (
                          <td key={j} className="px-4 py-3">
                            <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                          </td>
                        ))}
                      </tr>
                    ))
                  : sessions.map((session) => (
                      <SessionRow key={session.id} session={session} />
                    ))}
              </tbody>
            </table>
            {!isLoading && sessions.length === 0 && (
              <div className="px-6 py-10 text-center text-sm text-slate-400">No sessions yet</div>
            )}
          </div>
        </CardBody>
      </Card>

      <SessionModal open={sessionModalOpen} onClose={() => setSessionModalOpen(false)} />
    </div>
  )
}
