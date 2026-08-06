import { forwardRef, useId } from 'react'

const base =
  'w-full rounded-lg border px-3 py-2 text-sm transition-colors placeholder:text-ink-400 disabled:cursor-not-allowed disabled:opacity-60 bg-white text-ink-900 dark:bg-ink-800 dark:text-ink-100 dark:placeholder:text-ink-500'

const bordered = (error) =>
  error
    ? 'border-red-500 focus:border-red-500'
    : 'border-ink-300 focus:border-brand-500 dark:border-ink-700 dark:focus:border-brand-400'

/**
 * A labelled input.
 *
 * The label is tied to the field with a generated id rather than by wrapping, and the error is
 * announced — the previous version rendered the message in a `<p>` nothing pointed at, so a
 * screen reader read a valid-looking field and the error separately, with nothing joining them.
 */
const Input = forwardRef(({ label, error, hint, className = '', id, ...props }, ref) => {
  const generated = useId()
  const fieldId = id ?? generated
  const describedBy = error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={fieldId} className="label">
          {label}
        </label>
      )}
      <input
        id={fieldId}
        ref={ref}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...props}
        className={`${base} ${bordered(error)} ${className}`}
      />
      {hint && !error && (
        <p id={`${fieldId}-hint`} className="hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${fieldId}-error`} className="text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  )
})

Input.displayName = 'Input'
export default Input
export { base as fieldClasses, bordered as fieldBorder }
