import { Navigate, Route, Routes } from 'react-router-dom'
import { ROLES } from './config/roles'

import AppLayout from './layouts/AppLayout'
import UserLayout from './layouts/UserLayout'
import PersistLogin from './features/auth/PersistLogin'
import RequireAuth from './features/auth/RequireAuth'

// Public
import Login from './pages/public/Login'
import Apply from './pages/public/Apply'
import NotFound from './pages/public/NotFound'
import Unauthorized from './pages/public/Unauthorized'
import Landing from './pages/public/Landing'

// Shared
import Account from './pages/shared/Account'

// University
import UniversityOverview from './pages/university/Overview'
import Structure from './pages/university/Structure'
import Sessions from './pages/university/Sessions'
import Courses from './pages/university/Courses'
import Bursary from './pages/university/Bursary'
import Credentials from './pages/university/Credentials'

// Faculty
import FacultyOverview from './pages/faculty/Overview'
import Departments from './pages/faculty/Departments'
import OfferChains from './pages/faculty/OfferChains'

// Department
import DepartmentOverview from './pages/department/Overview'
import Programmes from './pages/department/Programmes'
import Admissions from './pages/department/Admissions'
import Lecturers from './pages/department/Lecturers'
import DepartmentStudents from './pages/department/Students'

// Lecturer
import LecturerOverview from './pages/lecturer/Overview'
import LecturerCourses from './pages/lecturer/Courses'
import SubmitGrade from './pages/lecturer/Grades'

// Student
import StudentOverview from './pages/student/Overview'
import Registration from './pages/student/Registration'
import Transcript from './pages/student/Transcript'
import Fees from './pages/student/Fees'

/**
 * Five role trees, and every page inside one has an API route behind it.
 *
 * The `RequireAuth` wrappers mirror the server's role gate rather than inventing a second
 * policy — see that component on why it is not a security boundary. Where the server admits
 * two roles to a route (a department registrar *or* the university above them), the tree
 * admits both too, so a university principal can reach a department's screens without a second
 * set of pages.
 */
export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Landing />} />
        <Route path="login" element={<Login />} />
        <Route path="apply" element={<Apply />} />
        <Route path="unauthorized" element={<Unauthorized />} />

        <Route element={<PersistLogin />}>
          {/* University */}
          <Route element={<RequireAuth allowedRoles={[ROLES.University]} />}>
            <Route path="university" element={<UserLayout />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<UniversityOverview />} />
              <Route path="structure" element={<Structure />} />
              <Route path="sessions" element={<Sessions />} />
              <Route path="courses" element={<Courses />} />
              <Route path="bursary" element={<Bursary />} />
              <Route path="credentials" element={<Credentials />} />
              <Route path="account" element={<Account />} />
            </Route>
          </Route>

          {/* Faculty office */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Faculty, ROLES.University]} />}>
            <Route path="faculty" element={<UserLayout />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<FacultyOverview />} />
              <Route path="departments" element={<Departments />} />
              <Route path="offer-chains" element={<OfferChains />} />
              <Route path="account" element={<Account />} />
            </Route>
          </Route>

          {/* Department registry */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Department, ROLES.University]} />}>
            <Route path="department" element={<UserLayout />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<DepartmentOverview />} />
              <Route path="programmes" element={<Programmes />} />
              <Route path="admissions" element={<Admissions />} />
              <Route path="lecturers" element={<Lecturers />} />
              <Route path="students" element={<DepartmentStudents />} />
              <Route path="account" element={<Account />} />
            </Route>
          </Route>

          {/* Lecturer */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Lecturer]} />}>
            <Route path="lecturer" element={<UserLayout />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<LecturerOverview />} />
              <Route path="courses" element={<LecturerCourses />} />
              <Route path="grades" element={<SubmitGrade />} />
              <Route path="account" element={<Account />} />
            </Route>
          </Route>

          {/* Student */}
          <Route element={<RequireAuth allowedRoles={[ROLES.Student, ROLES.University]} />}>
            <Route path="student" element={<UserLayout />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<StudentOverview />} />
              <Route path="registration" element={<Registration />} />
              <Route path="transcript" element={<Transcript />} />
              <Route path="fees" element={<Fees />} />
              <Route path="account" element={<Account />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
