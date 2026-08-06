import { Link } from 'react-router-dom'
import { LogOut, Menu, Moon, PanelLeft, Sun, UserRound } from 'lucide-react'
import useAuth from '../hooks/useAuth'
import useThemeStore from '../store/themeStore'
import { useSignOut } from '../features/auth/queries'
import { ROLE_BASE, ROLE_LABEL } from '../config/roles'

export default function Header({ onMenuClick, collapsed, onCollapseClick }) {
  const { role, loginId, scopeId } = useAuth()
  const { theme, toggle } = useThemeStore()
  const { mutate: signOut, isPending } = useSignOut()

  return (
    <header className="flex h-16 shrink-0 items-center gap-2 border-b border-ink-200 bg-white px-4 dark:border-ink-800 dark:bg-ink-900">
      <button
        onClick={onMenuClick}
        aria-label="Open navigation"
        className="rounded-lg p-2 text-ink-500 hover:bg-ink-100 dark:hover:bg-ink-800 md:hidden"
      >
        <Menu size={20} />
      </button>

      <button
        onClick={onCollapseClick}
        aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}
        className="hidden rounded-lg p-2 text-ink-500 hover:bg-ink-100 dark:hover:bg-ink-800 md:block"
      >
        <PanelLeft size={18} />
      </button>

      <div className="ml-auto flex items-center gap-1">
        <button
          onClick={toggle}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          className="rounded-lg p-2 text-ink-500 hover:bg-ink-100 dark:hover:bg-ink-800"
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        <Link
          to={`${ROLE_BASE[role] ?? ''}/account`}
          className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-ink-100 dark:hover:bg-ink-800"
        >
          <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-100 text-brand-700 dark:bg-brand-950 dark:text-brand-300">
            <UserRound size={16} aria-hidden="true" />
          </span>
          <span className="hidden text-left sm:block">
            <span className="block max-w-[12rem] truncate font-mono text-xs text-ink-900 dark:text-ink-100">
              {loginId}
            </span>
            <span className="block text-xs text-ink-500">
              {ROLE_LABEL[role]}
              {scopeId && scopeId !== loginId ? ` · ${scopeId}` : ''}
            </span>
          </span>
        </Link>

        <button
          onClick={() => signOut()}
          disabled={isPending}
          aria-label="Sign out"
          className="rounded-lg p-2 text-ink-500 hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-950/50"
        >
          <LogOut size={18} />
        </button>
      </div>
    </header>
  )
}
