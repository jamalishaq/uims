import {
  BookOpen,
  Building2,
  CalendarDays,
  ClipboardCheck,
  CreditCard,
  GraduationCap,
  KeyRound,
  LayoutDashboard,
  Layers,
  ScrollText,
  UserCog,
  Users,
  Wallet,
} from 'lucide-react'

/**
 * One entry per page, and every page has an API route behind it.
 *
 * That is the whole rule this file is now written to, and it is why it is so much shorter than
 * the one it replaces: the old nav listed attendance, assignments, exams, hostel, library and
 * thesis for a student, and the API has never had a route for any of them.
 *
 * Ordering matters for `student` and `lecturer` — `BottomNav` shows the first four on mobile.
 */
export const NAV = {
  university: [
    { label: 'Overview', to: 'overview', icon: LayoutDashboard },
    { label: 'Structure', to: 'structure', icon: Building2 },
    { label: 'Sessions', to: 'sessions', icon: CalendarDays },
    { label: 'Courses', to: 'courses', icon: BookOpen },
    { label: 'Bursary', to: 'bursary', icon: Wallet },
    { label: 'Credentials', to: 'credentials', icon: KeyRound },
  ],

  faculty: [
    { label: 'Overview', to: 'overview', icon: LayoutDashboard },
    { label: 'Departments', to: 'departments', icon: Building2 },
    { label: 'Offer chains', to: 'offer-chains', icon: Layers },
  ],

  department: [
    { label: 'Overview', to: 'overview', icon: LayoutDashboard },
    { label: 'Programmes', to: 'programmes', icon: Layers },
    { label: 'Admissions', to: 'admissions', icon: ClipboardCheck },
    { label: 'Lecturers', to: 'lecturers', icon: UserCog },
    { label: 'Students', to: 'students', icon: Users },
  ],

  lecturer: [
    { label: 'Overview', to: 'overview', icon: LayoutDashboard },
    { label: 'My courses', to: 'courses', icon: BookOpen },
    { label: 'Submit a grade', to: 'grades', icon: GraduationCap },
  ],

  student: [
    { label: 'Overview', to: 'overview', icon: LayoutDashboard },
    { label: 'Registration', to: 'registration', icon: BookOpen },
    { label: 'Transcript', to: 'transcript', icon: ScrollText },
    { label: 'Fees', to: 'fees', icon: CreditCard },
  ],
}
