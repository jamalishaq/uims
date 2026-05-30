const colors = {
  default: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300',
  indigo:  'bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300',
  violet:  'bg-violet-50 dark:bg-violet-950 text-violet-700 dark:text-violet-300',
  success: 'bg-emerald-50 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-400',
  warning: 'bg-amber-50 dark:bg-amber-950 text-amber-700 dark:text-amber-400',
  danger:  'bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-400',
}

export default function Badge({ children, color = 'default', className = '' }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors[color]} ${className}`}
    >
      {children}
    </span>
  )
}
