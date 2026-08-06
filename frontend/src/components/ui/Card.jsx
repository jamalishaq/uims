export default function Card({ children, className = '', ...props }) {
  return (
    <div {...props} className={`surface ${className}`}>
      {children}
    </div>
  )
}

export function CardHeader({ title, description, action, className = '' }) {
  return (
    <div
      className={`flex items-start justify-between gap-4 border-b border-ink-200 px-5 py-4 dark:border-ink-800 ${className}`}
    >
      <div className="min-w-0">
        <h2 className="truncate text-sm font-semibold text-ink-900 dark:text-ink-100">{title}</h2>
        {description && <p className="mt-0.5 hint">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

export function CardBody({ children, className = '' }) {
  return <div className={`px-5 py-4 ${className}`}>{children}</div>
}

export function CardFooter({ children, className = '' }) {
  return (
    <div
      className={`flex items-center justify-end gap-2 border-t border-ink-200 px-5 py-3 dark:border-ink-800 ${className}`}
    >
      {children}
    </div>
  )
}
