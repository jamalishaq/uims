/**
 * The five principals, exactly as the API's tokens name them.
 *
 * These strings are the `role` claim. They are not this app's vocabulary to choose: they come
 * out of a JWT that `identity.domain.values.Role` on the server produced, and a sixth entry
 * invented here would be a role no token can ever carry. `auth.md` in the repository root is
 * the design note.
 *
 * The old file had nine roles — super_admin, registrar, bursar, dean, HOD, applicant, alumni —
 * and the server has never issued a token for any of them.
 */
export const ROLES = {
  University: 'university',
  Faculty: 'faculty',
  Department: 'department',
  Lecturer: 'lecturer',
  Student: 'student',
}

export const ALL_ROLES = Object.values(ROLES)

/** Where each role's section of the app lives. */
export const ROLE_BASE = {
  university: '/university',
  faculty: '/faculty',
  department: '/department',
  lecturer: '/lecturer',
  student: '/student',
}

export const ROLE_HOME = {
  university: '/university/overview',
  faculty: '/faculty/overview',
  department: '/department/overview',
  lecturer: '/lecturer/overview',
  student: '/student/overview',
}

/**
 * What to call each principal on screen.
 *
 * A `university` token is section 6's *bursar* as much as it is the registry — it is one role
 * because the permissions are identical, and calling it "Bursary" here would be picking one of
 * the two jobs it does.
 */
export const ROLE_LABEL = {
  university: 'University',
  faculty: 'Faculty office',
  department: 'Department',
  lecturer: 'Lecturer',
  student: 'Student',
}

/**
 * What a principal types to log in — shown under the login field so nobody has to guess.
 *
 * A student's is their matric number; everybody else's is the id the system minted for the
 * thing they are.
 */
export const LOGIN_HINT = {
  university: 'the university id',
  faculty: 'your faculty id',
  department: 'your department id',
  lecturer: 'your staff id',
  student: 'your matric number',
}

/** Roles that get a bottom tab bar on mobile rather than a drawer: the ones with few pages. */
export const BOTTOM_NAV_ROLES = ['student', 'lecturer']
