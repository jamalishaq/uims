import useAuthStore from '../store/authStore'

export default function useAuth() {
  return useAuthStore((s) => s.getUser()) ?? {}
}
