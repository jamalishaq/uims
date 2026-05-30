# University Management System — Feature Specification

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TanStack Query v5, Zustand, Axios, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy (async), Alembic |
| Auth | JWT (access token in body, refresh token as httpOnly cookie) |
| WebSocket | FastAPI native WebSocket + ConnectionManager + Redis Pub/Sub (multi-worker) |
| RBAC | FastAPI dependency injection + `python-casbin` for role hierarchy |
| Payments | Paystack |
| Task Queue | Celery + Redis (emails, PDF generation, notifications) |
| Database | PostgreSQL |
| File Storage | S3-compatible (transcripts, thesis uploads, ID cards) |

---

## Organizational Structure

- **University** → **Faculty/College** → **Department** → **Program**
- Programs have a type: BSc, MSc, PhD, PGDE
- Each program defines: total credit hours required, core credits, elective credits, duration

---

## User Roles (Casbin hierarchy)

```
super_admin
└── registrar
└── bursar
└── dean
    └── hod
        └── lecturer
└── librarian
└── student
└── applicant
└── alumni
```

Each role inherits permissions from roles below it in its branch.

---

## Features

### 1. Admission & Application

**For applicants:**
- Online application form (personal info, program choice, qualifications)
- Document upload (credentials, passport photo)
- Application fee payment via Paystack
- Application status tracking (submitted → screening → accepted / rejected)
- Acceptance fee payment after admission offer
- Provisional admission letter download (PDF)

**For registrar / admin:**
- Application dashboard with filters (program, status, intake)
- Batch screening and decision workflow
- Admission offer generation
- Applicant → Student account promotion on acceptance fee payment

---

### 2. Student Registration & Records

- Matriculation number generation on full registration
- Student profile: bio-data, next-of-kin, medical info, photo
- Program and level assignment
- Student ID card generation (PDF/printable)
- Academic history: all semesters, courses, grades
- Status tracking: active, on leave, suspended, withdrawn, graduated

---

### 3. Academic Structure

**Course management:**
- Course code, title, credit hours, course type (core / elective / general studies)
- Prerequisites (enforced at registration)
- Assigned lecturer(s) per semester
- Maximum enrollment cap per section

**Academic calendar:**
- Sessions and semesters (first, second, summer)
- Key dates: registration open/close, lectures start/end, exam period, result release
- Holiday and event dates

**Timetable:**
- Lecture schedule per course section (day, time, venue)
- Conflict detection (lecturer double-booked, venue double-booked)
- Student personal timetable view

---

### 4. Course Registration

- Students register for courses each semester within credit load limits (min 15, max 21 credit hours)
- Prerequisites enforced automatically
- Add/drop period within the first two weeks
- Late registration with penalty fee
- Registrar can override or force-register a student
- Course registration receipt (PDF)

---

### 5. Attendance

- Lecturers mark attendance per course per lecture day
- 75% attendance rule enforced — students barred from exam if below threshold
- Student attendance dashboard (per course, percentage)
- HOD/Dean can view department-wide attendance reports

---

### 6. Assignments & Assessments

- Lecturer creates assignments with due dates, instructions, and file attachments
- Student submission with file upload
- Grading interface for lecturers (marks + feedback)
- Continuous assessment (CA) score recorded per course per student
- CA contributes to final grade alongside exam score

---

### 7. Examinations & Grading

**Exam management:**
- Exam timetable published per semester
- Venue and invigilator assignment
- Exam attendance marking

**Result processing workflow:**
- Lecturer submits raw scores (CA + exam)
- HOD reviews and approves
- Dean ratifies
- Registrar publishes — only then visible to students

**Grade computation:**
- Configurable grading scale per faculty (e.g. 70–100 = A = 5.0)
- Grade points × credit hours = weighted points
- GPA per semester, CGPA cumulative
- Failed courses flagged for carryover

**Carryover / repeat:**
- Failed course added to next registration automatically
- CGPA recalculated after carryover pass

---

### 8. Credit Hour System

- Each course has a credit hour value
- GPA = Σ(grade_points × credit_hours) / Σ(credit_hours)
- Graduation audit: checks total passed credits meet program requirements (core + elective + general)
- Prerequisite check: "must have passed 90 credit hours" style rules supported

---

### 9. Transcript & Graduation

- Official transcript generated as PDF (all semesters, courses, grades, GPA, CGPA)
- Graduation clearance checklist:
  - Minimum CGPA met
  - All required credits passed
  - No outstanding fees (bursary clearance)
  - Library clearance
  - Department clearance
- Degree certificate issuance tracking
- Convocation list generation

---

### 10. Finance & Fees

**Fee schedule:**
- Configurable fee types per semester: tuition, accommodation, library, department levy, exam fee
- Fees vary by program, level, and student type (full-time, part-time)

**Payments:**
- All payments via Paystack
- Payment receipt generation (PDF)
- Partial payment support with balance tracking
- Bursary dashboard: outstanding balances, payment history per student
- Financial clearance status (blocks result access and graduation if outstanding)

**Scholarships / waivers:**
- Scholarship and fee waiver records attached to student
- Waiver reduces fee obligation before payment

---

### 11. Hostel & Accommodation

- Hostel blocks, floors, rooms with capacity
- Student accommodation application per semester
- Room allocation and waitlist
- Accommodation fee tied to room type
- Eviction / voluntary checkout workflow

---

### 12. Library

- Book catalog (title, author, ISBN, copies available)
- Borrowing and return tracking
- Overdue fines calculation
- Student library clearance status
- Librarian dashboard

---

### 13. Notifications & Messaging

**Real-time (WebSocket):**
- Course-scoped group chat (students + lecturer in a course section)
- Result release notification
- Announcement push notifications

**Async (Celery + email):**
- Admission decision emails
- Payment confirmation emails
- Exam timetable release
- Result availability alerts
- Deadline reminders (registration close, fee due date)

**Notice board:**
- Announcements targeted by audience: university-wide, faculty, department, program, level
- Pinnable and expirable notices

---

### 14. Staff Management

- Non-academic staff accounts (admin officers, lab technicians, security)
- Staff profile: department, designation, employment type
- Staff directory

---

### 15. Thesis & Dissertation (Postgraduate)

- Topic registration and supervisor assignment
- Progress report submissions per semester
- Final document upload
- Supervisor review and approval workflow
- Defense scheduling

---

### 16. Reporting & Analytics (Admin / Dean / HOD)

- Enrollment statistics per program, level, semester
- Pass/fail rates per course and department
- Fee collection summary and outstanding balances
- Attendance compliance report
- CGPA distribution report
- Graduation rate trends

---

### 17. Alumni

- Automatic alumni record created on graduation
- Alumni portal: transcript download, verification letter request
- Alumni directory (opt-in)

---

## Features Dropped from Current System

| Removed | Reason |
|---|---|
| Secretary role | Replaced by Registrar, Bursar, HOD, Dean with scoped access |
| "Class" as core unit | Universities use Course enrollment, not fixed class groups |
| Form teacher / `is_form_teacher` | No equivalent in university structure |
| Report cards | Replaced by official transcript and GPA |
| Simple flat term model | Replaced by Session → Semester → Academic Calendar |

---

## Data Model Anchors

```
University
└── Faculty → Department → Program
                             └── requires: credit_hours, duration, degree_type

AcademicSession → Semester
                    └── CourseSection (Course × Lecturer × Semester)
                          └── CourseEnrollment (Student × CourseSection)
                                └── grade, grade_points, credit_hours, passed

Student
  └── program, level, status, cgpa
  └── CourseEnrollments (many)
  └── Payments (many)
  └── ClearanceStatus (bursary, library, department)
```
