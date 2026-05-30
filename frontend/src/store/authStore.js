import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { jwtDecode } from 'jwt-decode'

const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      rememberMe: false,

      setToken: (token) => set({ token }),
      setRememberMe: (rememberMe) => set({ rememberMe }),
      clearAuth: () => set({ token: null }),

      getUser: () => {
        const { token } = get()
        if (!token) return null
        try {
          return jwtDecode(token)
        } catch {
          return null
        }
      },
    }),
    {
      name: 'auth',
      partialize: (state) => ({
        token: state.rememberMe ? state.token : null,
        rememberMe: state.rememberMe,
      }),
    }
  )
)

export default useAuthStore
