import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const STORAGE_KEY = 'ums.theme'

/** Write the class Tailwind's `darkMode: 'class'` reads. The one place that touches the DOM. */
const apply = (theme) => {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', theme === 'dark')
  document.documentElement.dataset.theme = theme
}

/**
 * The starting theme: what was chosen last, else what the operating system prefers.
 *
 * Falling back to the OS preference rather than to light means somebody who runs their machine
 * dark does not get a white flash on their first visit, and it costs one media query.
 */
const initialTheme = () => {
  if (typeof window === 'undefined') return 'light'
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null')?.state?.theme
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // Corrupt or unreadable storage is not worth failing a page load over.
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const useThemeStore = create(
  persist(
    (set) => ({
      theme: initialTheme(),
      toggle: () =>
        set((state) => {
          const theme = state.theme === 'dark' ? 'light' : 'dark'
          apply(theme)
          return { theme }
        }),
      setTheme: (theme) => {
        apply(theme)
        set({ theme })
      },
    }),
    {
      name: STORAGE_KEY,
      /**
       * Re-apply on rehydration.
       *
       * The store this replaces toggled the class *inside* `toggle` and nowhere else, so a
       * persisted dark theme was remembered in `localStorage` and never actually applied after
       * a reload — the page came back light with the toggle showing dark.
       */
      onRehydrateStorage: () => (state) => apply(state?.theme ?? 'light'),
    }
  )
)

// The first paint, before React mounts. Without this the app renders light and then flips.
apply(useThemeStore.getState().theme)

export default useThemeStore
