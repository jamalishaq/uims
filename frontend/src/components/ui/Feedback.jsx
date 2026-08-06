import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'
import { errorMessage } from '../../lib/api'
import Spinner from './Spinner'

const notes = {
  info: {
    icon: Info,
    box: 'border-brand-200 bg-brand-50 text-brand-900 dark:border-brand-900 dark:bg-brand-950/60 dark:text-brand-100',
    mark: 'text-brand-600 dark:text-brand-400',
  },
  success: {
    icon: CheckCircle2,
    box: 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-100',
    mark: 'text-emerald-600 dark:text-emerald-400',
  },
  warning: {
    icon: AlertTriangle,
    box: 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-100',
    mark: 'text-amber-600 dark:text-amber-400',
  },
  danger: {
    icon: XCircle,
    box: 'border-red-200 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950/60 dark:text-red-100',
    mark: 'text-red-600 dark:text-red-400',
  },
}

export function Note({ tone = 'info', title, children, className = '' }) {
  const { icon: Icon, box, mark } = notes[tone]
  return (
    <div
      // `status` rather than `alert` for everything: an alert interrupts a screen reader
      // mid-sentence, which is right for a failure and rude for a confirmation.
      role={tone === 'danger' ? 'alert' : 'status'}
      className={`flex gap-3 rounded-lg border px-4 py-3 text-sm ${box} ${className}`}
    >
      <Icon size={18} className={`mt-0.5 shrink-0 ${mark}`} />
      <div className="min-w-0">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={title ? 'mt-0.5 opacity-90' : ''}>{children}</div>}
      </div>
    </div>
  )
}

/**
 * What went wrong, as the API said it.
 *
 * Renders the server's `detail` — the half written for a person — rather than a generic
 * message. The API's error envelope exists so a client does not have to invent prose, and the
 * refusals in this system are unusually worth reading: "no session-fee charge on record" and
 * "quota exhausted" tell a registrar what to do next in a way "Request failed" cannot.
 */
export function ErrorNote({ error, title = 'That did not work', className = '' }) {
  if (!error) return null
  return (
    <Note tone="danger" title={title} className={className}>
      {errorMessage(error)}
    </Note>
  )
}

/** The three states every fetched panel has, so no page reinvents them. */
export function Loading({ label = 'Loading…', className = '' }) {
  return (
    <div className={`flex items-center gap-3 px-5 py-8 text-sm text-ink-500 ${className}`}>
      <Spinner size="sm" />
      <span>{label}</span>
    </div>
  )
}
