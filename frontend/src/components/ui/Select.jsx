import { forwardRef, useId } from 'react'
import { fieldBorder, fieldClasses } from './Input'

const Select = forwardRef(({ label, error, hint, children, className = '', id, ...props }, ref) => {
  const generated = useId()
  const fieldId = id ?? generated

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={fieldId} className="label">
          {label}
        </label>
      )}
      <select
        id={fieldId}
        ref={ref}
        aria-invalid={error ? true : undefined}
        {...props}
        className={`${fieldClasses} ${fieldBorder(error)} ${className}`}
      >
        {children}
      </select>
      {hint && !error && <p className="hint">{hint}</p>}
      {error && <p className="text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  )
})

Select.displayName = 'Select'
export default Select
