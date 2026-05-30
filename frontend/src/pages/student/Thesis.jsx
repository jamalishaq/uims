import { useState } from 'react'
import toast from 'react-hot-toast'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Badge from '../../components/ui/Badge'
import Input from '../../components/ui/Input'
import Modal from '../../components/ui/Modal'
import { useMyThesis, useRegisterThesis, useSubmitThesis } from '../../features/thesis/queries'

const STATUS_COLORS = {
  approved: 'success',
  rejected: 'danger',
  submitted: 'warning',
  under_review: 'indigo',
  topic_submitted: 'indigo',
  in_progress: 'default',
}

function statusLabel(status) {
  if (!status) return 'Unknown'
  return status
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

const SUBMITTABLE_STATUSES = ['topic_submitted', 'in_progress']

export default function Thesis() {
  useTitle('Thesis')

  const { data: thesis, isLoading, error } = useMyThesis()
  const { mutate: registerThesis, isPending: registering } = useRegisterThesis()
  const { mutate: submitThesis, isPending: submitting } = useSubmitThesis()

  const [form, setForm] = useState({ title: '', supervisor_id: '', abstract: '' })
  const [formErrors, setFormErrors] = useState({})
  const [submitModal, setSubmitModal] = useState(false)
  const [fileUrl, setFileUrl] = useState('')

  const hasThesis = !!thesis && error?.response?.status !== 404
  const noThesis = !isLoading && (!thesis || error?.response?.status === 404)

  // Register form
  const handleFormChange = (field) => (e) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }))
    setFormErrors((prev) => ({ ...prev, [field]: undefined }))
  }

  const validateRegister = () => {
    const errors = {}
    if (!form.title.trim()) errors.title = 'Title is required.'
    if (!form.supervisor_id || isNaN(Number(form.supervisor_id)))
      errors.supervisor_id = 'Enter a valid lecturer user ID.'
    return errors
  }

  const handleRegister = () => {
    const errors = validateRegister()
    if (Object.keys(errors).length) {
      setFormErrors(errors)
      return
    }
    const body = {
      title: form.title.trim(),
      supervisor_id: Number(form.supervisor_id),
    }
    if (form.abstract.trim()) body.abstract = form.abstract.trim()

    registerThesis(body, {
      onSuccess: () => {
        toast.success('Thesis topic registered successfully.')
        setForm({ title: '', supervisor_id: '', abstract: '' })
      },
      onError: (err) => {
        const msg =
          err?.response?.data?.detail ??
          err?.response?.data?.message ??
          err?.message ??
          'Registration failed.'
        toast.error(msg)
      },
    })
  }

  // Submit document
  const handleSubmitDoc = () => {
    if (!fileUrl.trim()) {
      toast.error('Please enter a file URL.')
      return
    }
    submitThesis(
      { id: thesis.id, file_url: fileUrl.trim() },
      {
        onSuccess: () => {
          toast.success('Thesis document submitted successfully.')
          setSubmitModal(false)
          setFileUrl('')
        },
        onError: (err) => {
          const msg =
            err?.response?.data?.detail ??
            err?.response?.data?.message ??
            err?.message ??
            'Submission failed.'
          toast.error(msg)
        },
      }
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Thesis"
        subtitle="Register your thesis topic and track its progress."
      />

      {/* Loading skeleton */}
      {isLoading && (
        <Card>
          <CardBody>
            <div className="space-y-2">
              <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded animate-pulse w-2/3" />
              <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded animate-pulse w-1/2" />
            </div>
          </CardBody>
        </Card>
      )}

      {/* Thesis status card */}
      {hasThesis && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                My Thesis
              </h2>
              <Badge color={STATUS_COLORS[thesis.status] ?? 'default'}>
                {statusLabel(thesis.status)}
              </Badge>
            </div>
          </CardHeader>
          <CardBody>
            <dl className="space-y-3">
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Title</dt>
                <dd className="mt-0.5 text-sm font-medium text-slate-900 dark:text-slate-100">
                  {thesis.title ?? '—'}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-slate-500 dark:text-slate-400">Supervisor</dt>
                <dd className="mt-0.5 text-sm text-slate-700 dark:text-slate-300">
                  {thesis.supervisor?.name ??
                    thesis.supervisor?.full_name ??
                    thesis.supervisor_name ??
                    (thesis.supervisor_id ? `User #${thesis.supervisor_id}` : '—')}
                </dd>
              </div>
              {thesis.abstract && (
                <div>
                  <dt className="text-xs text-slate-500 dark:text-slate-400">Abstract</dt>
                  <dd className="mt-0.5 text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                    {thesis.abstract}
                  </dd>
                </div>
              )}
              {thesis.file_url && (
                <div>
                  <dt className="text-xs text-slate-500 dark:text-slate-400">Submitted File</dt>
                  <dd className="mt-0.5">
                    <a
                      href={thesis.file_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm text-indigo-600 dark:text-indigo-400 hover:underline break-all"
                    >
                      {thesis.file_url}
                    </a>
                  </dd>
                </div>
              )}
            </dl>

            {SUBMITTABLE_STATUSES.includes(thesis.status) && (
              <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
                <Button variant="primary" onClick={() => setSubmitModal(true)}>
                  Submit Document
                </Button>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* Register form */}
      {noThesis && (
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
              Register Thesis Topic
            </h2>
          </CardHeader>
          <CardBody>
            <div className="space-y-4 max-w-lg">
              <Input
                label="Title"
                placeholder="Enter your thesis title"
                value={form.title}
                onChange={handleFormChange('title')}
                error={formErrors.title}
              />
              <Input
                label="Supervisor User ID"
                type="number"
                placeholder="Enter lecturer user ID"
                value={form.supervisor_id}
                onChange={handleFormChange('supervisor_id')}
                error={formErrors.supervisor_id}
              />
              <div className="flex flex-col gap-1">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                  Abstract{' '}
                  <span className="text-slate-400 font-normal">(optional)</span>
                </label>
                <textarea
                  rows={4}
                  placeholder="Brief summary of your research…"
                  value={form.abstract}
                  onChange={handleFormChange('abstract')}
                  className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 dark:focus:border-indigo-400 transition-colors resize-none"
                />
              </div>
              <div className="flex justify-end">
                <Button variant="primary" loading={registering} onClick={handleRegister}>
                  Register Topic
                </Button>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Submit document modal */}
      <Modal
        open={submitModal}
        onClose={() => setSubmitModal(false)}
        title="Submit Thesis Document"
      >
        <div className="space-y-4">
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
              File URL
            </label>
            <input
              type="url"
              value={fileUrl}
              onChange={(e) => setFileUrl(e.target.value)}
              placeholder="https://drive.google.com/…"
              className="w-full rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-3 py-2 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-colors"
            />
            <p className="text-xs text-slate-400 dark:text-slate-500">
              Paste a publicly accessible file link (Google Drive, OneDrive, etc.).
            </p>
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setSubmitModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" loading={submitting} onClick={handleSubmitDoc}>
              Submit
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
