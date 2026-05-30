/**
 * Shared render helper that wraps components with all required providers:
 * QueryClient, BrowserRouter, and a fresh auth store.
 *
 * Usage:
 *   import { render, screen } from '../test-utils'
 *   render(<MyComponent />)
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { render as rtlRender } from '@testing-library/react'

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

export function render(ui, { route = '/', queryClient, ...options } = {}) {
  const qc = queryClient ?? makeQueryClient()
  function Wrapper({ children }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[route]}>
          {children}
        </MemoryRouter>
      </QueryClientProvider>
    )
  }
  return rtlRender(ui, { wrapper: Wrapper, ...options })
}

// re-export testing-library utilities (render is the custom wrapped one above)
export { screen, waitFor, fireEvent, act, within, renderHook, cleanup } from '@testing-library/react'
