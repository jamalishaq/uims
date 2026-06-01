import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { useNavigate, useLocation } from 'react-router-dom'
import { jwtDecode } from 'jwt-decode'
import toast from 'react-hot-toast'
import { login } from '../../features/auth/queries'
import useAuthStore from '../../store/authStore'
import { ROLE_HOME } from '../../config/roles'
import Input from '../../components/ui/Input'
import Button from '../../components/ui/Button'
import useTitle from '../../hooks/useTitle'

const schema = z.object({
  email:      z.string().email('Enter a valid email'),
  password:   z.string().min(1, 'Password is required'),
  rememberMe: z.boolean(),
})

const DEMO_ROLES = [
  { label: 'Super Admin', email: 'admin@school.edu', password: 'admin123' },
  { label: 'Registrar',   email: 'registrar@school.edu',  password: 'registrar123'  },
  { label: 'Bursar',      email: 'bursar@school.edu',     password: 'bursar123'     },
  { label: 'Dean',        email: 'dean@school.edu',       password: 'dean123'       },
  { label: 'HOD',         email: 'hod@school.edu',        password: 'hod123'        },
  { label: 'Lecturer',    email: 'lecturer@school.edu',   password: 'lecturer123'   },
  { label: 'Student',     email: 'student@school.edu',    password: 'student123'    },
  { label: 'Applicant',   email: 'applicant@school.edu',  password: 'applicant123'  },
  { label: 'Alumni',      email: 'alumni@school.edu',     password: 'alumni123'     },
]

export default function Login() {
  useTitle('Sign in')
  const navigate = useNavigate()
  const location = useLocation()
  const setToken = useAuthStore((s) => s.setToken)
  const setRememberMe = useAuthStore((s) => s.setRememberMe)

  const { register, handleSubmit, formState: { errors } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '', rememberMe: false },
  })

  const { mutate, isPending } = useMutation({
    mutationFn: login,
    onSuccess: (data, variables) => {
      setRememberMe(variables.rememberMe)
      setToken(data.access_token)
      const { role } = jwtDecode(data.access_token)
      const from = location.state?.from?.pathname
      navigate(from ?? ROLE_HOME[role?.toLowerCase()] ?? '/login', { replace: true })
    },
    onError: () => toast.error('Invalid email or password'),
  })

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-4">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-indigo-600 mb-4">
            <span className="text-white font-bold text-lg">U</span>
          </div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">Sign in</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            University Management System
          </p>
        </div>

        {/* Form */}
        {false && (
        <form
          onSubmit={handleSubmit((v) => mutate(v))}
          className="bg-white dark:bg-slate-900 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800 p-6 space-y-4"
        >
          <Input
            label="Email"
            type="email"
            placeholder="you@university.edu"
            error={errors.email?.message}
            autoComplete="email"
            {...register('email')}
          />
          <Input
            label="Password"
            type="password"
            placeholder="••••••••"
            error={errors.password?.message}
            autoComplete="current-password"
            {...register('password')}
          />
          <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 cursor-pointer select-none">
            <input
              type="checkbox"
              className="rounded border-slate-300 dark:border-slate-600 text-indigo-600"
              {...register('rememberMe')}
            />
            Remember me
          </label>
          <Button type="submit" className="w-full" loading={isPending}>
            Sign in
          </Button>
        </form>
        )}

        {/* Demo logins */}
        <div className="mt-6 bg-white dark:bg-slate-900 rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 p-4">
          <p className="text-xs font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wide mb-3 text-center">
            Demo accounts
          </p>
          <div className="flex flex-wrap gap-2 justify-center">
            {DEMO_ROLES.map(({ label, email, password }) => (
              <button
                key={email}
                type="button"
                disabled={isPending}
                onClick={() => mutate({ email, password, rememberMe: false })}
                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-indigo-50 dark:hover:bg-indigo-900/40 hover:text-indigo-700 dark:hover:text-indigo-300 border border-slate-200 dark:border-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Login as {label}
              </button>
            ))}
          </div>
        </div>

        <p className="mt-4 text-center text-sm text-slate-500 dark:text-slate-400">
          Applying for admission?{' '}
          <a href="/apply" className="text-indigo-600 dark:text-indigo-400 hover:underline font-medium">
            Apply here
          </a>
        </p>
      </div>
    </div>
  )
}
