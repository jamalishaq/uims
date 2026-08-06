import { Inbox } from 'lucide-react'

/**
 * Nothing here — and, where it matters, why.
 *
 * `description` is not decoration in this app. Several empty states are *meaningful*: a
 * department with no programmes has not published any, an applicant list that is empty means
 * nobody applied rather than that a filter is wrong, and a student with no academic record is a
 * fresher rather than a missing row. Saying so is the difference between an empty table and a
 * bug report.
 */
export default function EmptyState({ icon: Icon = Inbox, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="rounded-full bg-ink-100 p-3 dark:bg-ink-800">
        <Icon size={20} className="text-ink-400" aria-hidden="true" />
      </div>
      <p className="mt-3 text-sm font-medium text-ink-700 dark:text-ink-300">{title}</p>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-ink-500 dark:text-ink-400">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
