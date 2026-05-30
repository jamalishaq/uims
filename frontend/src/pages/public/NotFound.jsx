import { useNavigate } from 'react-router-dom'
import Button from '../../components/ui/Button'
import useTitle from '../../hooks/useTitle'

export default function NotFound() {
  useTitle('Page not found')
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-4">
      <div className="text-center">
        <p className="text-6xl font-bold text-indigo-600 dark:text-indigo-400 mb-4">404</p>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-2">
          Page not found
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
          The page you're looking for doesn't exist.
        </p>
        <Button onClick={() => navigate(-1)}>Go back</Button>
      </div>
    </div>
  )
}
