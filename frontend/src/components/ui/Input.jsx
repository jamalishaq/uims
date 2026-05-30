import { forwardRef } from 'react'

const Input = forwardRef(({ label, error, hint, className = '', ...props }, ref) => (
  <div className="flex flex-col gap-1">
    {label && (
      <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
        {label}
      </label>
    )}
    <input
      ref={ref}
      {...props}
      className={`w-full rounded-lg border px-3 py-2 text-sm bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 transition-colors
        ${error
          ? 'border-red-500 focus:ring-red-500/20'
          : 'border-slate-200 dark:border-slate-700 focus:border-indigo-500 dark:focus:border-indigo-400 focus:ring-indigo-500/20 dark:focus:ring-indigo-400/20'
        }
        focus:outline-none focus:ring-2 ${className}`}
    />
    {hint && !error && <p className="text-xs text-slate-500 dark:text-slate-400">{hint}</p>}
    {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
  </div>
))

Input.displayName = 'Input'
export default Input
