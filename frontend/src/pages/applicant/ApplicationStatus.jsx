import { ClipboardList, Mail, Phone } from 'lucide-react'
import useTitle from '../../hooks/useTitle'
import PageHeader from '../../components/PageHeader'
import Card, { CardBody, CardHeader } from '../../components/ui/Card'
import Badge from '../../components/ui/Badge'
import { useMyApplication } from '../../features/admission/queries'

function statusColor(status) {
  if (!status) return 'warning'
  const s = status.toLowerCase()
  if (s === 'approved' || s === 'admitted') return 'success'
  if (s === 'rejected') return 'danger'
  if (s === 'under_review' || s === 'review') return 'indigo'
  return 'warning'
}

function statusLabel(status) {
  if (!status) return 'Pending Review'
  const s = status.toLowerCase()
  if (s === 'under_review') return 'Under Review'
  return status.charAt(0).toUpperCase() + status.slice(1)
}

function InfoRow({ label, value }) {
  if (!value) return null
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-0.5 sm:gap-4 py-2 border-b border-slate-100 dark:border-slate-800 last:border-0">
      <span className="text-xs font-medium text-slate-500 dark:text-slate-400 sm:w-36 shrink-0">{label}</span>
      <span className="text-sm text-slate-900 dark:text-slate-100">{value}</span>
    </div>
  )
}

export default function ApplicationStatus() {
  useTitle('Application Status')

  const { data: application } = useMyApplication()

  return (
    <div>
      <PageHeader
        title="Application Status"
        subtitle="Track the progress of your admission application."
      />

      {application ? (
        <div className="flex flex-col gap-5 max-w-lg">
          {/* Status card */}
          <Card>
            <CardBody className="flex items-center gap-4 py-6">
              <div className="flex-shrink-0 flex items-center justify-center w-12 h-12 rounded-full bg-indigo-50 dark:bg-indigo-950">
                <ClipboardList className="text-indigo-600 dark:text-indigo-400" size={24} />
              </div>
              <div>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-1">Current Status</p>
                <Badge color={statusColor(application.status)} className="text-sm px-3 py-1">
                  {statusLabel(application.status)}
                </Badge>
              </div>
            </CardBody>
          </Card>

          {/* Application details */}
          <Card>
            <CardHeader>
              <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">Application Details</h2>
            </CardHeader>
            <CardBody>
              {application.id && (
                <InfoRow label="Reference" value={`#${application.id}`} />
              )}
              <InfoRow
                label="Applicant"
                value={[application.first_name, application.last_name].filter(Boolean).join(' ') || null}
              />
              <InfoRow label="Program" value={application.program_name ?? application.program ?? null} />
              <InfoRow label="Session" value={application.session_name ?? application.session ?? null} />
              <InfoRow label="Phone" value={application.phone ?? null} />
              <InfoRow label="Date of Birth" value={application.date_of_birth ?? null} />
              <InfoRow label="Submitted" value={
                application.created_at
                  ? new Date(application.created_at).toLocaleDateString('en-NG', {
                      year: 'numeric', month: 'long', day: 'numeric',
                    })
                  : null
              } />
            </CardBody>
          </Card>

          {/* Decision message if available */}
          {application.decision_note && (
            <Card>
              <CardBody>
                <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Admissions Note</p>
                <p className="text-sm text-slate-700 dark:text-slate-300">{application.decision_note}</p>
              </CardBody>
            </Card>
          )}
        </div>
      ) : (
        /* No cached data — generic message */
        <Card className="max-w-lg">
          <CardBody className="py-8 flex flex-col items-center text-center gap-5">
            <div className="flex items-center justify-center w-14 h-14 rounded-full bg-amber-50 dark:bg-amber-950">
              <ClipboardList className="text-amber-500" size={28} />
            </div>

            <div>
              <p className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-1">
                Application Under Review
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Your application has been received and is currently being reviewed by our
                admissions team. You will be contacted once a decision has been made.
              </p>
            </div>

            <div className="w-full border-t border-slate-100 dark:border-slate-800 pt-5 flex flex-col gap-3 text-sm text-slate-600 dark:text-slate-400">
              <p className="font-medium text-slate-700 dark:text-slate-300">Need help? Contact Admissions</p>
              <div className="flex items-center justify-center gap-2">
                <Mail size={15} />
                <a href="mailto:admissions@university.edu.ng" className="hover:underline">
                  admissions@university.edu.ng
                </a>
              </div>
              <div className="flex items-center justify-center gap-2">
                <Phone size={15} />
                <a href="tel:+2348000000000" className="hover:underline">
                  +234 800 000 0000
                </a>
              </div>
            </div>
          </CardBody>
        </Card>
      )}
    </div>
  )
}
