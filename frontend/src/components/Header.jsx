import { Menu, PanelLeftClose, PanelLeftOpen, Sun, Moon, Bell } from 'lucide-react'
import useAuth from '../hooks/useAuth'
import useThemeStore from '../store/themeStore'

export default function Header({ onMenuClick, collapsed, onCollapseClick }) {
  const { dark, toggle } = useThemeStore()
  const { username, role } = useAuth()
  const initials = username ? username.slice(0, 2).toUpperCase() : '?'

  return (
    <header className="h-16 shrink-0 flex items-center gap-3 px-4 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
      {/* Mobile hamburger */}
      <button
        onClick={onMenuClick}
        className="md:hidden text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors"
      >
        <Menu size={20} />
      </button>

      {/* Desktop collapse toggle */}
      <button
        onClick={onCollapseClick}
        className="hidden md:block text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors"
      >
        {collapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={20} />}
      </button>

      <div className="flex-1" />

      {/* Dark mode toggle */}
      <button
        onClick={toggle}
        className="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors"
        aria-label="Toggle dark mode"
      >
        {dark ? <Sun size={20} /> : <Moon size={20} />}
      </button>

      {/* Notifications */}
      <button className="relative text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white transition-colors">
        <Bell size={20} />
      </button>

      {/* User avatar */}
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-semibold shrink-0">
          {initials}
        </div>
        <div className="hidden sm:block">
          <p className="text-sm font-medium text-slate-900 dark:text-slate-100 leading-tight">
            {username ?? '—'}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 capitalize leading-tight">
            {role?.replace('_', ' ') ?? ''}
          </p>
        </div>
      </div>
    </header>
  )
}
