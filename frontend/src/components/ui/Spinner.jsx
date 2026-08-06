const sizes = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-10 w-10' }

export default function Spinner({ size = 'md', className = '' }) {
  return (
    <span
      // `currentColor` on the leading edge rather than a fixed brand colour: this sits inside
      // buttons of four different variants, and an indigo spinner on a red danger button is the
      // kind of thing that only shows up in the one state nobody screenshots.
      role="status"
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-2 border-current border-t-transparent opacity-60 ${sizes[size]} ${className}`}
    />
  )
}
