export const ROLES = {
  SuperAdmin: 'super_admin',
  Registrar:  'registrar',
  Bursar:     'bursar',
  Dean:       'dean',
  HOD:        'hod',
  Lecturer:   'lecturer',
  Student:    'student',
  Applicant:  'applicant',
  Alumni:     'alumni',
}

export const ROLE_BASE = {
  super_admin: '/admin',
  registrar:   '/registrar',
  bursar:      '/bursar',
  dean:        '/dean',
  hod:         '/hod',
  lecturer:    '/lecturer',
  student:     '/student',
  applicant:   '/applicant',
  alumni:      '/alumni',
}

export const ROLE_HOME = {
  super_admin: '/admin/dashboard',
  registrar:   '/registrar/dashboard',
  bursar:      '/bursar/dashboard',
  dean:        '/dean/dashboard',
  hod:         '/hod/dashboard',
  lecturer:    '/lecturer/dashboard',
  student:     '/student/dashboard',
  applicant:   '/applicant/dashboard',
  alumni:      '/alumni/dashboard',
}

// Roles that use bottom tab nav on mobile instead of hamburger drawer
export const BOTTOM_NAV_ROLES = ['student', 'applicant', 'alumni']
