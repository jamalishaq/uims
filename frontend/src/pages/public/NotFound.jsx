import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import { ROLE_HOME } from '../../config/roles'

export default function NotFound() {
  useTitle('Page not found')
  const { role, isSignedIn } = useAuth()

  return (
    <div className="grid min-h-dvh place-items-center bg-ink-100 px-4 dark:bg-ink-950">
      <div className="w-full max-w-md text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-ink-200 dark:bg-ink-800">
          <Compass size={22} className="text-ink-500" aria-hidden="true" />
        </div>
        <h1 className="mt-4 text-xl font-semibold text-ink-900 dark:text-ink-50">
          There is nothing here
        </h1>
        <p className="mt-2 text-sm text-ink-500 dark:text-ink-400">
          The page you asked for does not exist.
        </p>
        <Link
          to={isSignedIn ? (ROLE_HOME[role] ?? '/login') : '/login'}
          className="mt-6 inline-block rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          {isSignedIn ? 'Go to my pages' : 'Sign in'}
        </Link>
      </div>
    </div>
  )
}
