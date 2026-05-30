import { useNavigate } from 'react-router-dom'
import Button from '../../components/ui/Button'
import useTitle from '../../hooks/useTitle'

export default function Unauthorized() {
  useTitle('Unauthorized')
  const navigate = useNavigate()

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 p-4">
      <div className="text-center">
        <p className="text-6xl font-bold text-red-500 mb-4">403</p>
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-2">
          Access denied
        </h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
          You don't have permission to view this page.
        </p>
        <Button onClick={() => navigate(-1)}>Go back</Button>
      </div>
    </div>
  )
}
