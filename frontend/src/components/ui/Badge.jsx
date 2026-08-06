const tones = {
  neutral: 'bg-ink-100 text-ink-700 dark:bg-ink-800 dark:text-ink-300',
  brand: 'bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-300',
  success: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  warning: 'bg-amber-50 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
  danger: 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300',
}

export default function Badge({ children, tone = 'neutral', className = '' }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

/**
 * The tone each domain state is shown in, in one table.
 *
 * Worth centralising because two of these are easy to get backwards. **`declined` is not a
 * failure** — it is an applicant exercising a choice, and it returns their place to the quota,
 * so it reads neutral rather than red. **`no_offer` is not an error either**: every cycle in the
 * chain was full, which is a normal outcome of a fully automatic process, and colouring it red
 * would suggest somebody made a mistake.
 *
 * What *is* red is `probation` and `refused` — the two states somebody has to act on.
 */
export const STATUS_TONE = {
  // admissions
  applied: 'neutral',
  screened: 'brand',
  offered: 'brand',
  accepted: 'success',
  declined: 'neutral',
  matriculated: 'success',
  no_offer: 'neutral',
  // academic standing
  good_standing: 'success',
  probation: 'danger',
  // enrollment
  registered: 'brand',
  awaiting_grade: 'warning',
  finalized: 'success',
  refused: 'danger',
  // payment intents
  initiated: 'warning',
  confirmed: 'success',
  failed: 'danger',
  abandoned: 'neutral',
}

/** Turn `no_offer_available` into `No offer available` without a second mapping table. */
export const humanise = (value = '') =>
  String(value).replace(/[_-]+/g, ' ').replace(/^./, (c) => c.toUpperCase())

export function StatusBadge({ status, className = '' }) {
  if (!status) return null
  return (
    <Badge tone={STATUS_TONE[status] ?? 'neutral'} className={className}>
      {humanise(status)}
    </Badge>
  )
}
