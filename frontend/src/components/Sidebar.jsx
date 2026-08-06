import { NavLink } from 'react-router-dom'
import { GraduationCap, X } from 'lucide-react'
import { NAV } from '../config/nav'
import { ROLE_BASE, ROLE_LABEL } from '../config/roles'
import useAuth from '../hooks/useAuth'

/**
 * The primary navigation, and the only place that says which unit you are acting for.
 *
 * That last part matters more here than in most apps. Authority in this system is
 * `(role, scope)` — a department registrar's permissions mean nothing without *which
 * department* — so the sidebar prints the scope under the role. Somebody logged in as
 * `dept-csc` who thinks they are logged in as `dept-mth` will read every screen wrongly and
 * every refusal as a bug.
 */
export default function Sidebar({ collapsed = false, onClose }) {
  const { role, scopeId, loginId } = useAuth()
  const links = NAV[role] ?? []
  const base = ROLE_BASE[role] ?? ''

  return (
    <aside
      className={`flex h-full flex-col border-r border-ink-800 bg-ink-950 transition-[width] duration-200 ${
        collapsed ? 'w-16' : 'w-64'
      }`}
    >
      <div className="flex h-16 shrink-0 items-center gap-2.5 border-b border-ink-800/80 px-4">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand-600">
          <GraduationCap size={17} className="text-white" aria-hidden="true" />
        </div>
        {!collapsed && (
          <span className="truncate text-sm font-semibold tracking-tight text-white">
            University MS
          </span>
        )}
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close navigation"
            className="ml-auto rounded-lg p-1.5 text-ink-400 hover:bg-ink-800 hover:text-white md:hidden"
          >
            <X size={18} />
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="border-b border-ink-800/80 px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-ink-500">
            {ROLE_LABEL[role] ?? 'Signed in'}
          </p>
          <p className="truncate font-mono text-sm text-ink-200" title={scopeId ?? loginId}>
            {scopeId ?? loginId}
          </p>
        </div>
      )}

      <nav className="flex-1 space-y-0.5 overflow-y-auto p-2" aria-label="Main">
        {links.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={`${base}/${to}`}
            onClick={onClose}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-brand-600 text-white'
                  : 'text-ink-300 hover:bg-ink-800 hover:text-white'
              } ${collapsed ? 'justify-center' : ''}`
            }
          >
            <Icon size={18} className="shrink-0" aria-hidden="true" />
            {!collapsed && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
