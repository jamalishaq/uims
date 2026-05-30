import { NavLink, useNavigate } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { NAV } from '../config/nav'
import { ROLE_BASE } from '../config/roles'
import useAuth from '../hooks/useAuth'
import useAuthStore from '../store/authStore'
import { logout } from '../features/auth/queries'

export default function Sidebar({ role, collapsed = false, onClose }) {
  const { sub: userId } = useAuth()
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const navigate = useNavigate()
  const links = NAV[role] ?? []
  const base = ROLE_BASE[role] ?? ''

  const { mutate: doLogout } = useMutation({
    mutationFn: logout,
    onSettled: () => {
      clearAuth()
      navigate('/login')
    },
  })

  return (
    <aside
      className={`flex flex-col h-full bg-indigo-950 transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Logo */}
      <div className="flex h-16 shrink-0 items-center px-4 border-b border-indigo-900">
        {collapsed ? (
          <span className="text-white font-bold text-lg mx-auto">U</span>
        ) : (
          <span className="text-white font-semibold text-sm tracking-wide">UniMS</span>
        )}
      </div>

      {/* Nav links */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-0.5">
        {links.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={`${base}/${to}`}
            onClick={onClose}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-700 text-white'
                  : 'text-slate-300 hover:bg-indigo-900 hover:text-white'
              }`
            }
          >
            <Icon size={18} className="shrink-0" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Logout */}
      <div className="shrink-0 border-t border-indigo-900 p-3">
        <button
          onClick={() => doLogout()}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm font-medium text-slate-300 hover:bg-indigo-900 hover:text-white transition-colors"
        >
          <LogOut size={18} className="shrink-0" />
          {!collapsed && <span>Logout</span>}
        </button>
      </div>
    </aside>
  )
}
