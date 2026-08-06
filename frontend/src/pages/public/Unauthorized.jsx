import { Link } from 'react-router-dom'
import { ShieldOff } from 'lucide-react'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import { ROLE_HOME, ROLE_LABEL } from '../../config/roles'

export default function Unauthorized() {
  useTitle('Not permitted')
  const { role, scopeId } = useAuth()

  return (
    <div className="grid min-h-dvh place-items-center bg-ink-100 px-4 dark:bg-ink-950">
      <div className="w-full max-w-md text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-amber-100 dark:bg-amber-950">
          <ShieldOff size={22} className="text-amber-700 dark:text-amber-400" aria-hidden="true" />
        </div>
        <h1 className="mt-4 text-xl font-semibold text-ink-900 dark:text-ink-50">
          That page is not yours to open
        </h1>
        {/* Saying *what* they are signed in as, because the usual cause is being signed in to
            the wrong unit rather than lacking permission — authority here is (role, scope). */}
        <p className="mt-2 text-sm text-ink-500 dark:text-ink-400">
          You are signed in as{' '}
          <strong className="text-ink-700 dark:text-ink-300">
            {ROLE_LABEL[role] ?? 'an unknown role'}
          </strong>
          {scopeId && <> for <span className="font-mono">{scopeId}</span></>}. If that is not the
          unit you meant, sign out and sign in again.
        </p>
        <div className="mt-6 flex items-center justify-center gap-3">
          <Link
            to={ROLE_HOME[role] ?? '/login'}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            Go to my pages
          </Link>
          <Link
            to="/login"
            className="rounded-lg border border-ink-300 px-4 py-2 text-sm font-medium text-ink-700 hover:bg-ink-50 dark:border-ink-700 dark:text-ink-300 dark:hover:bg-ink-800"
          >
            Sign in as someone else
          </Link>
        </div>
      </div>
    </div>
  )
}
