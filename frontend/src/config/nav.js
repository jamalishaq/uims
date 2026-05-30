import {
  LayoutDashboard,
  BookOpen,
  ClipboardList,
  FileText,
  GraduationCap,
  CreditCard,
  Users,
  BarChart3,
  CheckSquare,
  DollarSign,
  Building2,
  Calendar,
  ScrollText,
  List,
  Library,
  Home,
  Award,
} from 'lucide-react'

export const NAV = {
  // Bottom-nav order matters: BottomNav shows first 5
  student: [
    { label: 'Dashboard',   to: 'dashboard',   icon: LayoutDashboard },
    { label: 'Courses',     to: 'courses',     icon: BookOpen },
    { label: 'Enrollments', to: 'enrollments', icon: List },
    { label: 'Grades',      to: 'grades',      icon: GraduationCap },
    { label: 'Payments',    to: 'payments',    icon: CreditCard },
    { label: 'Attendance',  to: 'attendance',  icon: CheckSquare },
    { label: 'Assignments', to: 'assignments', icon: ClipboardList },
    { label: 'Exams',       to: 'exams',       icon: FileText },
    { label: 'Hostel',      to: 'hostel',      icon: Home },
    { label: 'Library',     to: 'library',     icon: Library },
    { label: 'Thesis',      to: 'thesis',      icon: Award },
  ],

  applicant: [
    { label: 'Dashboard', to: 'dashboard', icon: LayoutDashboard },
    { label: 'Apply',     to: 'apply',     icon: FileText },
    { label: 'My Status', to: 'status',    icon: CheckSquare },
  ],

  lecturer: [
    { label: 'Dashboard',    to: 'dashboard',   icon: LayoutDashboard },
    { label: 'My Sections',  to: 'sections',    icon: BookOpen },
    { label: 'Attendance',   to: 'attendance',  icon: CheckSquare },
    { label: 'Assignments',  to: 'assignments', icon: ClipboardList },
    { label: 'Grades',       to: 'grades',      icon: GraduationCap },
  ],

  hod: [
    { label: 'Dashboard',  to: 'dashboard',  icon: LayoutDashboard },
    { label: 'Attendance', to: 'attendance', icon: CheckSquare },
    { label: 'Reports',    to: 'reports',    icon: BarChart3 },
  ],

  dean: [
    { label: 'Dashboard', to: 'dashboard', icon: LayoutDashboard },
    { label: 'Overview',  to: 'overview',  icon: Building2 },
    { label: 'Reports',   to: 'reports',   icon: BarChart3 },
  ],

  registrar: [
    { label: 'Dashboard',    to: 'dashboard',    icon: LayoutDashboard },
    { label: 'Applications', to: 'applications', icon: FileText },
    { label: 'Students',     to: 'students',     icon: Users },
  ],

  bursar: [
    { label: 'Dashboard',    to: 'dashboard', icon: LayoutDashboard },
    { label: 'Fee Schedule', to: 'fees',      icon: DollarSign },
    { label: 'Payments',     to: 'payments',  icon: CreditCard },
  ],

  super_admin: [
    { label: 'Dashboard', to: 'dashboard', icon: LayoutDashboard },
    { label: 'Structure', to: 'structure', icon: Building2 },
    { label: 'Sessions',  to: 'sessions',  icon: Calendar },
    { label: 'Courses',   to: 'courses',   icon: BookOpen },
    { label: 'Users',     to: 'users',     icon: Users },
  ],

  alumni: [
    { label: 'Dashboard',  to: 'dashboard',  icon: LayoutDashboard },
    { label: 'Transcript', to: 'transcript', icon: ScrollText },
  ],
}
