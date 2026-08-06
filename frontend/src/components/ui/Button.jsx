import Spinner from './Spinner'

/**
 * Variants named by intent, not by colour.
 *
 * `danger` is for acts that destroy or refuse; `caution` is for the ones that are correct,
 * routine and *irreversible in bulk* — opening a session, which bills a whole cohort, and
 * publishing a policy, which cannot be republished. The system has several of those and the
 * previous kit had no way to say so, which meant "Open session" looked exactly like "Save".
 */
const variants = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 active:bg-brand-800 shadow-sm',
  secondary:
    'border border-ink-300 bg-white text-ink-700 hover:bg-ink-50 dark:border-ink-700 dark:bg-ink-800 dark:text-ink-200 dark:hover:bg-ink-700',
  caution: 'bg-amber-600 text-white hover:bg-amber-700 active:bg-amber-800 shadow-sm',
  danger: 'bg-red-600 text-white hover:bg-red-700 active:bg-red-800 shadow-sm',
  ghost: 'text-ink-600 hover:bg-ink-100 dark:text-ink-400 dark:hover:bg-ink-800',
}

const sizes = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-10 px-4 text-sm gap-2',
  lg: 'h-11 px-5 text-sm gap-2',
}

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  className = '',
  disabled,
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      {...props}
      disabled={disabled || loading}
      // `aria-busy` rather than only a spinner: a screen reader gets nothing from a rotating
      // SVG, and this is the one state where the button looks enabled and is not.
      aria-busy={loading || undefined}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  )
}
