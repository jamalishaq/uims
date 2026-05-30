import { useMemo } from 'react'
import { jwtDecode } from 'jwt-decode'
import useAuthStore from '../store/authStore'

export default function useAuth() {
  const token = useAuthStore((s) => s.token)
  return useMemo(() => {
    if (!token) return {}
    try {
      return jwtDecode(token)
    } catch {
      return {}
    }
  }, [token])
}
