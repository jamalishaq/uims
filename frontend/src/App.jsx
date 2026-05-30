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
import StudentCourses from './pages/student/Courses'
import StudentEnrollments from './pages/student/Enrollments'
import StudentGrades from './pages/student/Grades'
import StudentPayments from './pages/student/Payments'
import StudentAttendance from './pages/student/Attendance'
import StudentAssignments from './pages/student/Assignments'
import StudentExams from './pages/student/Exams'
import StudentHostel from './pages/student/Hostel'
import StudentLibrary from './pages/student/Library'
import StudentThesis from './pages/student/Thesis'

// Applicant pages
import ApplicantDashboard from './pages/applicant/Dashboard'
import ApplicationForm from './pages/applicant/ApplicationForm'
import ApplicationStatus from './pages/applicant/ApplicationStatus'

// Lecturer pages
import LecturerDashboard from './pages/lecturer/Dashboard'
import LecturerSections from './pages/lecturer/Sections'
import LecturerAttendance from './pages/lecturer/Attendance'
import LecturerAssignments from './pages/lecturer/Assignments'
import LecturerGrades from './pages/lecturer/Grades'

// HOD pages
import HODDashboard from './pages/hod/Dashboard'
import HODAttendance from './pages/hod/Attendance'
import HODReports from './pages/hod/Reports'

// Dean pages
import DeanDashboard from './pages/dean/Dashboard'
import DeanOverview from './pages/dean/Overview'
import DeanReports from './pages/dean/Reports'

// Registrar pages
import RegistrarDashboard from './pages/registrar/Dashboard'
import Applications from './pages/registrar/Applications'
import Students from './pages/registrar/Students'
import StudentDetail from './pages/registrar/StudentDetail'

// Bursar pages
import BursarDashboard from './pages/bursar/Dashboard'
import BursarFees from './pages/bursar/Fees'
import BursarPayments from './pages/bursar/Payments'

// Super Admin pages
import SuperAdminDashboard from './pages/super_admin/Dashboard'
import AcademicStructure from './pages/super_admin/AcademicStructure'
import Sessions from './pages/super_admin/Sessions'
import AdminCourses from './pages/super_admin/Courses'
import AdminUsers from './pages/super_admin/Users'

// Alumni pages
import AlumniDashboard from './pages/alumni/Dashboard'
import AlumniTranscript from './pages/alumni/Transcript'

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
              <Route path="courses"     element={<StudentCourses />} />
              <Route path="enrollments" element={<StudentEnrollments />} />
              <Route path="grades"      element={<StudentGrades />} />
              <Route path="payments"    element={<StudentPayments />} />
              <Route path="attendance"  element={<StudentAttendance />} />
              <Route path="assignments" element={<StudentAssignments />} />
              <Route path="exams"       element={<StudentExams />} />
              <Route path="hostel"      element={<StudentHostel />} />
              <Route path="library"     element={<StudentLibrary />} />
              <Route path="thesis"      element={<StudentThesis />} />
            </Route>
          </Route>

          {/* Applicant */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Applicant]} />}>
            <Route path="applicant" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<ApplicantDashboard />} />
              <Route path="apply"     element={<ApplicationForm />} />
              <Route path="status"    element={<ApplicationStatus />} />
            </Route>
          </Route>

          {/* Lecturer */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Lecturer]} />}>
            <Route path="lecturer" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"   element={<LecturerDashboard />} />
              <Route path="sections"    element={<LecturerSections />} />
              <Route path="attendance"  element={<LecturerAttendance />} />
              <Route path="assignments" element={<LecturerAssignments />} />
              <Route path="grades"      element={<LecturerGrades />} />
            </Route>
          </Route>

          {/* HOD */}
          <Route element={<RequireAuth allowedRoles={[ROLES.HOD]} />}>
            <Route path="hod" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"  element={<HODDashboard />} />
              <Route path="attendance" element={<HODAttendance />} />
              <Route path="reports"    element={<HODReports />} />
            </Route>
          </Route>

          {/* Dean */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Dean]} />}>
            <Route path="dean" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<DeanDashboard />} />
              <Route path="overview"  element={<DeanOverview />} />
              <Route path="reports"   element={<DeanReports />} />
            </Route>
          </Route>

          {/* Registrar */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Registrar]} />}>
            <Route path="registrar" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"        element={<RegistrarDashboard />} />
              <Route path="applications"     element={<Applications />} />
              <Route path="students"         element={<Students />} />
              <Route path="students/:studentId" element={<StudentDetail />} />
            </Route>
          </Route>

          {/* Bursar */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Bursar]} />}>
            <Route path="bursar" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<BursarDashboard />} />
              <Route path="fees"      element={<BursarFees />} />
              <Route path="payments"  element={<BursarPayments />} />
            </Route>
          </Route>

          {/* Super Admin */}
          <Route element={<RequireAuth allowedRoles={[ROLES.SuperAdmin]} />}>
            <Route path="admin" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<SuperAdminDashboard />} />
              <Route path="structure" element={<AcademicStructure />} />
              <Route path="sessions"  element={<Sessions />} />
              <Route path="courses"   element={<AdminCourses />} />
              <Route path="users"     element={<AdminUsers />} />
            </Route>
          </Route>

          {/* Alumni */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Alumni]} />}>
            <Route path="alumni" element={<UserLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard"  element={<AlumniDashboard />} />
              <Route path="transcript" element={<AlumniTranscript />} />
            </Route>
          </Route>

        </Route>

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
