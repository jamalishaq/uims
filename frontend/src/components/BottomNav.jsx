import { NavLink } from 'react-router-dom'
import { NAV } from '../config/nav'
import { ROLE_BASE } from '../config/roles'

export default function BottomNav({ role }) {
  const links = (NAV[role] ?? []).slice(0, 5)
  const base = ROLE_BASE[role] ?? ''

  return (
    <nav className="fixed bottom-0 inset-x-0 z-10 md:hidden flex bg-white dark:bg-slate-900 border-t border-slate-200 dark:border-slate-800 safe-area-inset-bottom">
      {links.map(({ label, to, icon: Icon }) => (
        <NavLink
          key={to}
          to={`${base}/${to}`}
          className={({ isActive }) =>
            `flex flex-col items-center justify-center flex-1 py-2 gap-0.5 text-xs font-medium transition-colors ${
              isActive
                ? 'text-indigo-600 dark:text-indigo-400'
                : 'text-slate-500 dark:text-slate-400'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Icon
                size={20}
                className={isActive ? 'text-indigo-600 dark:text-indigo-400' : ''}
              />
              <span>{label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
