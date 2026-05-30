import { Route, Routes, Navigate } from 'react-router-dom'
import { ROLES } from './config/roles'

import AppLayout from './layouts/AppLayout'
import UserLayout from './layouts/UserLayout'
import PersistLogin from './features/auth/PersistLogin'
import RequireAuth from './features/auth/RequireAuth'

// Public pages
import Login from './pages/public/Login'
import Apply from './pages/public/Apply'
import NotFound from './pages/public/NotFound'
import Unauthorized from './pages/public/Unauthorized'

// Student pages
import StudentDashboard from './pages/student/Dashboard'

// Applicant pages
import ApplicantDashboard from './pages/applicant/Dashboard'

// Lecturer pages
import LecturerDashboard from './pages/lecturer/Dashboard'

// HOD pages
import HODDashboard from './pages/hod/Dashboard'

// Dean pages
import DeanDashboard from './pages/dean/Dashboard'

// Registrar pages
import RegistrarDashboard from './pages/registrar/Dashboard'

// Bursar pages
import BursarDashboard from './pages/bursar/Dashboard'

// Super Admin pages
import SuperAdminDashboard from './pages/super_admin/Dashboard'

// Alumni pages
import AlumniDashboard from './pages/alumni/Dashboard'

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        {/* Public */}
        <Route index element={<Navigate to="/login" replace />} />
        <Route path="login" element={<Login />} />
        <Route path="apply" element={<Apply />} />
        <Route path="unauthorized" element={<Unauthorized />} />

        {/* Authenticated */}
        <Route element={<PersistLogin />}>

          {/* Student */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Student]} />}>
            <Route path="student" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"   element={<StudentDashboard />} />
              {/* TODO: courses, timetable, attendance, assignments, exams, grades, payments, library, hostel */}
            </Route>
          </Route>

          {/* Applicant */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Applicant]} />}>
            <Route path="applicant" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"   element={<ApplicantDashboard />} />
              {/* TODO: application */}
            </Route>
          </Route>

          {/* Lecturer */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Lecturer]} />}>
            <Route path="lecturer" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"   element={<LecturerDashboard />} />
              {/* TODO: courses, attendance, assignments, grades, timetable */}
            </Route>
          </Route>

          {/* HOD */}
          <Route element={<RequireAuth allowedRoles={[ROLES.HOD]} />}>
            <Route path="hod" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"   element={<HODDashboard />} />
              {/* TODO: courses, attendance, scores, staff, reports */}
            </Route>
          </Route>

          {/* Dean */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Dean]} />}>
            <Route path="dean" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"   element={<DeanDashboard />} />
              {/* TODO: departments, scores, reports */}
            </Route>
          </Route>

          {/* Registrar */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Registrar]} />}>
            <Route path="registrar" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"   element={<RegistrarDashboard />} />
              {/* TODO: applications, students, registration, calendar */}
            </Route>
          </Route>

          {/* Bursar */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Bursar]} />}>
            <Route path="bursar" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"   element={<BursarDashboard />} />
              {/* TODO: fees, payments, clearances, waivers */}
            </Route>
          </Route>

          {/* Super Admin */}
          <Route element={<RequireAuth allowedRoles={[ROLES.SuperAdmin]} />}>
            <Route path="admin" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"   element={<SuperAdminDashboard />} />
              {/* TODO: structure, users, sessions, grading, settings */}
            </Route>
          </Route>

          {/* Alumni */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Alumni]} />}>
            <Route path="alumni" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"   element={<AlumniDashboard />} />
              {/* TODO: transcript, directory */}
            </Route>
          </Route>

        </Route>

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
