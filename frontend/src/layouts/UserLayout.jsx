import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import useAuth from '../hooks/useAuth'
import { BOTTOM_NAV_ROLES } from '../config/roles'
import Sidebar from '../components/Sidebar'
import Header from '../components/Header'
import BottomNav from '../components/BottomNav'

export default function UserLayout() {
  const { role } = useAuth()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const hasBottomNav = BOTTOM_NAV_ROLES.includes(role)

  return (
    <div className="flex h-dvh overflow-hidden bg-ink-100 dark:bg-ink-950">
      <div className="hidden shrink-0 md:flex">
        <Sidebar collapsed={collapsed} />
      </div>

      {drawerOpen && (
        <div
          className="fixed inset-0 z-20 bg-ink-950/60 md:hidden"
          onClick={() => setDrawerOpen(false)}
          aria-hidden="true"
        />
      )}

      <div
        className={`fixed inset-y-0 left-0 z-30 transition-transform duration-200 md:hidden ${
          drawerOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <Sidebar onClose={() => setDrawerOpen(false)} />
      </div>

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Header
          onMenuClick={() => setDrawerOpen(true)}
          collapsed={collapsed}
          onCollapseClick={() => setCollapsed((c) => !c)}
        />
        <main
          className={`flex-1 overflow-y-auto p-4 md:p-6 ${hasBottomNav ? 'pb-24 md:pb-6' : ''}`}
        >
          {/* `max-w-6xl` rather than full bleed: these are forms and tables, and a line of text
              or a two-column form stretched across a 32-inch monitor is unreadable. */}
          <div className="mx-auto w-full max-w-6xl animate-fade-up">
            <Outlet />
          </div>
        </main>
      </div>

      {hasBottomNav && <BottomNav role={role} />}
    </div>
  )
}
