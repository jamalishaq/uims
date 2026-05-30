import { useState } from 'react'
import toast from 'react-hot-toast'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { CheckCircle } from 'lucide-react'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody } from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import Select from '../../components/ui/Select'
import Badge from '../../components/ui/Badge'
import { useApply } from '../../features/admission/queries'
import { usePrograms, useSessions } from '../../features/academic/queries'

const schema = z.object({
  program_id:    z.string().min(1, 'Program is required'),
  session_id:    z.string().min(1, 'Session is required'),
  first_name:    z.string().min(1, 'First name is required').max(100),
  last_name:     z.string().min(1, 'Last name is required').max(100),
  phone:         z.string().min(7, 'Enter a valid phone number').max(20),
  address:       z.string().min(5, 'Address is required').max(300),
  date_of_birth: z.string().min(1, 'Date of birth is required'),
})

function statusColor(status) {
  if (!status) return 'warning'
  const s = status.toLowerCase()
  if (s === 'approved' || s === 'admitted') return 'success'
  if (s === 'rejected') return 'danger'
  if (s === 'under_review' || s === 'review') return 'indigo'
  return 'warning'
}

export default function ApplicationForm() {
  useTitle('Apply for Admission')

  const [submitted, setSubmitted]       = useState(false)
  const [application, setApplication]  = useState(null)
  const [alreadyApplied, setAlreadyApplied] = useState(false)

  const { data: programs = [], isLoading: programsLoading } = usePrograms()
  const { data: sessions = [], isLoading: sessionsLoading } = useSessions()
  const { mutate: apply, isPending: applying } = useApply()

  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      program_id:    '',
      session_id:    '',
      first_name:    '',
      last_name:     '',
      phone:         '',
      address:       '',
      date_of_birth: '',
    },
  })

  const onSubmit = (values) => {
    const payload = {
      ...values,
      program_id: Number(values.program_id),
      session_id: Number(values.session_id),
    }

    apply(payload, {
      onSuccess: (data) => {
        setApplication(data)
        setSubmitted(true)
        toast.success('Application submitted successfully!')
      },
      onError: (err) => {
        const status = err?.response?.status
        const msg    = err?.response?.data?.detail || err?.response?.data?.message || err?.message || 'Submission failed.'

        // Treat 400 as "already applied"
        if (status === 400) {
          setAlreadyApplied(true)
          toast.error('You have already submitted an application.')
        } else {
          toast.error(msg)
        }
      },
    })
  }

  // --- Success state ---
  if (submitted && application) {
    return (
      <div>
        <PageHeader title="Application Submitted" />
        <Card className="max-w-lg">
          <CardBody className="py-8 flex flex-col items-center text-center gap-4">
            <CheckCircle className="text-emerald-500" size={48} />
            <div>
              <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
                Application received!
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                Your application has been submitted and is currently under review.
              </p>
            </div>
            {application.id && (
              <p className="text-sm text-slate-600 dark:text-slate-300">
                Reference:{' '}
                <span className="font-mono font-semibold">#{application.id}</span>
              </p>
            )}
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-500 dark:text-slate-400">Status:</span>
              <Badge color={statusColor(application.status)}>
                {application.status ?? 'Pending Review'}
              </Badge>
            </div>
          </CardBody>
        </Card>
      </div>
    )
  }

  // --- Already applied state ---
  if (alreadyApplied) {
    return (
      <div>
        <PageHeader title="Apply for Admission" />
        <Card className="max-w-lg">
          <CardBody className="py-8 text-center">
            <Badge color="warning" className="mb-3">Already Applied</Badge>
            <p className="text-sm text-slate-600 dark:text-slate-300 mt-2">
              You have already submitted an application. Visit the{' '}
              <strong>Application Status</strong> page to track its progress.
            </p>
          </CardBody>
        </Card>
      </div>
    )
  }

  return (
    <div>
      <PageHeader
        title="Apply for Admission"
        subtitle="Complete all fields and submit your application."
      />

      <Card className="max-w-2xl">
        <CardBody>
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-5">
            {/* Program & Session */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Controller
                name="program_id"
                control={control}
                render={({ field }) => (
                  <Select
                    label="Program"
                    error={errors.program_id?.message}
                    disabled={programsLoading}
                    {...field}
                  >
                    <option value="">Select program</option>
                    {programs.map((p) => (
                      <option key={p.id} value={String(p.id)}>{p.name}</option>
                    ))}
                  </Select>
                )}
              />

              <Controller
                name="session_id"
                control={control}
                render={({ field }) => (
                  <Select
                    label="Session"
                    error={errors.session_id?.message}
                    disabled={sessionsLoading}
                    {...field}
                  >
                    <option value="">Select session</option>
                    {sessions.map((s) => (
                      <option key={s.id} value={String(s.id)}>{s.name}</option>
                    ))}
                  </Select>
                )}
              />
            </div>

            {/* Name */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="First Name"
                placeholder="e.g. John"
                error={errors.first_name?.message}
                {...register('first_name')}
              />
              <Input
                label="Last Name"
                placeholder="e.g. Doe"
                error={errors.last_name?.message}
                {...register('last_name')}
              />
            </div>

            {/* Phone & DOB */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Input
                label="Phone Number"
                type="tel"
                placeholder="+2348012345678"
                error={errors.phone?.message}
                {...register('phone')}
              />
              <Input
                label="Date of Birth"
                type="date"
                error={errors.date_of_birth?.message}
                {...register('date_of_birth')}
              />
            </div>

            {/* Address */}
            <div className="flex flex-col gap-1">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Address
              </label>
              <textarea
                rows={3}
                placeholder="Your residential address"
                className={`w-full rounded-lg border px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 resize-none transition-colors focus:outline-none focus:ring-2 ${
                  errors.address
                    ? 'border-red-500 focus:ring-red-500/20'
                    : 'border-slate-200 dark:border-slate-700 focus:border-indigo-500 focus:ring-indigo-500/20'
                }`}
                {...register('address')}
              />
              {errors.address && (
                <p className="text-xs text-red-600 dark:text-red-400">{errors.address.message}</p>
              )}
            </div>

            <div className="flex justify-end pt-2">
              <Button type="submit" loading={applying} size="lg">
                Submit Application
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
    </div>
  )
}
