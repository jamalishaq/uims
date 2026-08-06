export default function PageHeader({ title, description, action, children }) {
  return (
    <header className="mb-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold tracking-tight text-ink-900 dark:text-ink-50">
            {title}
          </h1>
          {description && (
            <p className="mt-1 max-w-2xl text-sm text-ink-500 dark:text-ink-400">{description}</p>
          )}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      {children && <div className="mt-4">{children}</div>}
    </header>
  )
}

/**
 * A figure worth reading at a glance.
 *
 * `caption` exists because two numbers in this system are routinely confused for one another —
 * a programme's *places claimed* and its *applicant cohort* count different populations and do
 * not add up. A tile that showed "12" with no caption is how a department discovers in
 * September that it admitted people it never saw.
 */
export function StatTile({ label, value, caption, tone = 'neutral' }) {
  const accents = {
    neutral: 'text-ink-900 dark:text-ink-50',
    brand: 'text-brand-700 dark:text-brand-300',
    success: 'text-emerald-700 dark:text-emerald-400',
    warning: 'text-amber-700 dark:text-amber-400',
    danger: 'text-red-700 dark:text-red-400',
  }
  return (
    <div className="surface px-4 py-3.5">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-500 dark:text-ink-400">
        {label}
      </p>
      <p className={`tabular mt-1 text-2xl font-semibold ${accents[tone]}`}>{value}</p>
      {caption && <p className="mt-1 hint">{caption}</p>}
    </div>
  )
}

/** A label/value row, for the many places this app renders one record's fields. */
export function Detail({ label, value, mono = false }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-ink-100 py-2.5 last:border-0 dark:border-ink-800">
      <dt className="text-sm text-ink-500 dark:text-ink-400">{label}</dt>
      <dd
        className={`text-sm font-medium text-ink-900 dark:text-ink-100 ${mono ? 'tabular font-mono' : ''}`}
      >
        {value ?? <span className="font-normal text-ink-400">—</span>}
      </dd>
    </div>
  )
}
