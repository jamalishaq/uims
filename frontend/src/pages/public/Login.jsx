import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { GraduationCap } from 'lucide-react'
import Button from '../../components/ui/Button'
import Input from '../../components/ui/Input'
import { ErrorNote } from '../../components/ui/Feedback'
import { useSignIn } from '../../features/auth/queries'
import useAuth from '../../hooks/useAuth'
import useTitle from '../../hooks/useTitle'
import { ROLE_HOME } from '../../config/roles'

/**
 * One form for all five levels.
 *
 * There is deliberately **no role picker**. The server decides what a login id is: the token it
 * issues carries the role, and asking somebody to choose one first would let them pick wrong
 * and be told "invalid credentials" for a password that was perfectly correct. A student types
 * their matric number, everybody else the id the system minted for them, and the same field
 * takes both.
 */
export default function Login() {
  useTitle('Sign in')
  const navigate = useNavigate()
  const location = useLocation()
  const { isSignedIn, role } = useAuth()
  const { mutate: signIn, isPending, error, reset } = useSignIn()

  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')

  // Clear a stale refusal as soon as they change something, so the message belongs to what is
  // currently in the boxes rather than to an attempt two edits ago.
  useEffect(() => {
    if (error) reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loginId, password])

  if (isSignedIn && role) {
    return <Navigate to={ROLE_HOME[role] ?? '/'} replace />
  }

  const submit = (event) => {
    event.preventDefault()
    signIn(
      { loginId: loginId.trim(), password },
      {
        onSuccess: (session) => {
          const home = ROLE_HOME[session.principal.role] ?? '/'
          navigate(location.state?.from?.pathname ?? home, { replace: true })
        },
      }
    )
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      {/* The panel exists to make the login page feel like part of a university rather than a
          bare form, and it is hidden below `lg` — on a phone it would push the fields under
          the fold, which is the one thing a login page must never do. */}
      <div className="relative hidden overflow-hidden bg-ink-950 lg:block">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-800/40 via-ink-950 to-ink-950" />
        <div className="relative flex h-full flex-col justify-between p-12">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-600">
              <GraduationCap size={20} className="text-white" aria-hidden="true" />
            </div>
            <span className="text-lg font-semibold tracking-tight text-white">University MS</span>
          </div>
          <div className="max-w-md">
            <h2 className="text-3xl font-semibold leading-tight tracking-tight text-white">
              Admissions, records, registration and fees.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-ink-400">
              One system, from an application through matriculation to a transcript. Sign in at
              your own level — university, faculty, department, lecturer or student.
            </p>
          </div>
          <p className="text-xs text-ink-600">
            Applying for admission?{' '}
            <Link to="/apply" className="text-ink-400 underline underline-offset-4">
              You do not need an account.
            </Link>
          </p>
        </div>
      </div>

      <div className="flex items-center justify-center bg-white px-6 py-12 dark:bg-ink-950">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-600">
              <GraduationCap size={20} className="text-white" aria-hidden="true" />
            </div>
          </div>

          <h1 className="text-2xl font-semibold tracking-tight text-ink-900 dark:text-ink-50">
            Sign in
          </h1>
          <p className="mt-1.5 text-sm text-ink-500 dark:text-ink-400">
            Students sign in with their matric number. Staff and offices use the id issued to
            them.
          </p>

          <form onSubmit={submit} className="mt-8 space-y-4">
            <Input
              label="Matric number or id"
              name="login_id"
              autoComplete="username"
              autoFocus
              required
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              placeholder="260591001"
            />
            <Input
              label="Password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />

            {/* One message for every refusal, because the server sends one: an unknown id and a
                wrong password are deliberately indistinguishable, so that nobody can sort
                guessed matric numbers into real and unreal. */}
            <ErrorNote error={error} title="Could not sign you in" />

            <Button type="submit" size="lg" loading={isPending} className="w-full">
              Sign in
            </Button>
          </form>

          <p className="mt-6 text-xs leading-relaxed text-ink-500 dark:text-ink-400">
            Applying for admission? The{' '}
            <Link to="/apply" className="font-medium text-brand-600 dark:text-brand-400">
              application form
            </Link>{' '}
            is open to everyone and needs no account.
          </p>
        </div>
      </div>
    </div>
  )
}
