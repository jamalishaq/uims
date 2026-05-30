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
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      {/* Desktop / tablet sidebar */}
      <div className="hidden md:flex shrink-0">
        <Sidebar role={role} collapsed={collapsed} />
      </div>

      {/* Mobile drawer backdrop */}
      {drawerOpen && (
        <div
          className="fixed inset-0 z-20 bg-black/50 md:hidden"
          onClick={() => setDrawerOpen(false)}
        />
      )}

      {/* Mobile drawer */}
      <div
        className={`fixed inset-y-0 left-0 z-30 md:hidden transition-transform duration-200 ${
          drawerOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <Sidebar role={role} onClose={() => setDrawerOpen(false)} />
      </div>

      {/* Main content */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Header
          onMenuClick={() => setDrawerOpen(true)}
          collapsed={collapsed}
          onCollapseClick={() => setCollapsed((c) => !c)}
        />
        <main
          className={`flex-1 overflow-y-auto p-4 md:p-6 ${
            hasBottomNav ? 'pb-20 md:pb-6' : ''
          }`}
        >
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom nav */}
      {hasBottomNav && <BottomNav role={role} />}
    </div>
  )
}
