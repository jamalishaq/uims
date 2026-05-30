import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const useThemeStore = create(
  persist(
    (set) => ({
      dark: false,
      toggle: () =>
        set((s) => {
          const next = !s.dark
          document.documentElement.classList.toggle('dark', next)
          return { dark: next }
        }),
    }),
    { name: 'theme' }
  )
)

export default useThemeStore
