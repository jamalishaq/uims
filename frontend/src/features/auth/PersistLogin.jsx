import { useEffect, useRef, useState } from 'react'
import { Outlet } from 'react-router-dom'
import useAuthStore from '../../store/authStore'
import api from '../../lib/api'
import Spinner from '../../components/ui/Spinner'

export default function PersistLogin() {
  const [loading, setLoading] = useState(true)
  const token = useAuthStore((s) => s.token)
  const setToken = useAuthStore((s) => s.setToken)
  const effectRan = useRef(false)

  useEffect(() => {
    if (effectRan.current) return
    effectRan.current = true

    if (token) {
      setLoading(false)
      return
    }

    api
      .post('/auth/refresh')
      .then(({ data }) => setToken(data.access_token))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 dark:bg-slate-950">
        <Spinner size="lg" />
      </div>
    )
  }

  return <Outlet />
}
