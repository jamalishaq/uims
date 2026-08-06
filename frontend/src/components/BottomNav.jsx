import { NavLink } from 'react-router-dom'
import { NAV } from '../config/nav'
import { ROLE_BASE } from '../config/roles'

const VISIBLE = 4

/**
 * Mobile tab bar for the two roles with few enough pages to fit one.
 *
 * Four tabs, not five: a fifth "More" that opened the drawer would duplicate the hamburger two
 * inches away. `student` and `lecturer` both have four or fewer pages, which is why they are
 * the roles that get this — `BOTTOM_NAV_ROLES` in `config/roles.js` says so.
 */
export default function BottomNav({ role }) {
  const links = (NAV[role] ?? []).slice(0, VISIBLE)
  const base = ROLE_BASE[role] ?? ''

  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-20 flex border-t border-ink-200 bg-white pb-[env(safe-area-inset-bottom)] dark:border-ink-800 dark:bg-ink-900 md:hidden"
    >
      {links.map(({ label, to, icon: Icon }) => (
        <NavLink
          key={to}
          to={`${base}/${to}`}
          className={({ isActive }) =>
            `flex flex-1 flex-col items-center gap-1 py-2.5 text-[11px] font-medium transition-colors ${
              isActive ? 'text-brand-600 dark:text-brand-400' : 'text-ink-500'
            }`
          }
        >
          <Icon size={19} aria-hidden="true" />
          <span className="truncate px-1">{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
