"""Faculty & Department over HTTP: grade submission, the placement read, and the 403.

These tests seed through repositories rather than over HTTP, because this context has no use
case that creates a faculty, a department, a program, a lecturer or a session. That is the gap
the router's docstring names, and seeding around it here is how the two routes that *do* exist
get exercised.
"""

from httpx import AsyncClient

from faculty_department.domain.department import Department
from faculty_department.domain.lecturer import Lecturer
from faculty_department.domain.program import Program
from faculty_department.domain.session import Semester, SemesterOrdinal, Session
from faculty_department.domain.values import AcademicYear


async def _seed_calendar(repos, *, open_session: bool = True) -> None:
    departments = repos.departments()
    programs = repos.programs()
    sessions = repos.sessions()

    await departments.add(
        Department(
            department_id="dept-csc", faculty_id="fac-sci", name="Computer Science", code="CSC"
        )
    )
    await programs.add(
        Program.create(
            program_id="prog-csc", department_id="dept-csc", name="BSc Computer Science", code="CSC"
        )
    )
    session = Session.plan(
        session_id="sess-2026",
        academic_year=AcademicYear(2026),
        semesters=[
            Semester("sem-1", SemesterOrdinal.FIRST),
            Semester("sem-2", SemesterOrdinal.SECOND),
        ],
    )
    if open_session:
        session.open()
    await sessions.add(session)


async def _seed_course(client: AsyncClient, api: str) -> None:
    """Register the course in the catalog, over HTTP, because that context does have use cases.

    A grade submission reaches Academic Records through the bus, and Academic Records asks the
    catalog what the course is worth before it will record anything. So a grade cannot be
    submitted for a course the catalog has never heard of — see the test that pins it.
    """
    response = await client.post(
        f"{api}/course-catalog/courses",
        json={
            "course_id": "csc101",
            "department_id": "dept-csc",
            "code": "CSC101",
            "title": "Introduction to Computer Science",
            "credit_units": 3,
        },
    )
    assert response.status_code == 201, response.text


async def _seed_lecturer(repos, *, assigned_to: str | None = "csc101") -> None:
    lecturers = repos.lecturers()
    lecturer = Lecturer(lecturer_id="lec-1", department_id="dept-csc", full_name="Ada Lovelace")
    if assigned_to is not None:
        lecturer.assign_to_course(assigned_to, "sess-2026")
    await lecturers.add(lecturer)


class TestSubmittingAGrade:
    async def test_an_assigned_lecturer_may_submit(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_calendar(repos)
        await _seed_lecturer(repos)
        await _seed_course(client, api)

        response = await client.post(
            f"{api}/faculty-department/grade-submissions",
            json={
                "lecturer_id": "lec-1",
                "session_id": "sess-2026",
                "student_id": "stu-1",
                "course_id": "csc101",
                "semester_id": "sem-1",
                "score": 78,
            },
        )
        assert response.status_code == 201, response.text
        assert response.json() == {
            "student_id": "stu-1",
            "course_id": "csc101",
            "semester_id": "sem-1",
            "grade": 78,
        }

    async def test_a_submitted_grade_reaches_academic_records_synchronously(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """The whole event path, end to end, through one HTTP call.

        ``SubmitGrade`` publishes ``GradeSubmitted``; the bus hands it to Academic Records'
        handler; that context asks Course Catalog what the course is worth through the live
        ``CourseCreditPort`` adapter, and writes the transcript line. None of those three
        contexts imports either of the others — the composition root introduced them — so a
        record existing here is the only proof the wiring is right.
        """
        await _seed_calendar(repos)
        await _seed_lecturer(repos)
        await _seed_course(client, api)

        await client.post(
            f"{api}/faculty-department/grade-submissions",
            json={
                "lecturer_id": "lec-1",
                "session_id": "sess-2026",
                "student_id": "stu-1",
                "course_id": "csc101",
                "semester_id": "sem-1",
                "score": 78,
            },
        )

        record = await client.get(f"{api}/academic-records/records/stu-1")
        assert record.status_code == 200, record.text
        body = record.json()
        assert body["cgpa"] == "5.00", "78 is an A on the confirmed scale, worth 5.0"
        assert body["total_units"] == 3, "the units came from the catalog, over a query port"
        assert body["grades"][0]["letter"] == "A"

    async def test_a_grade_for_a_course_the_catalog_does_not_know_is_refused(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """And the refusal travels back out through the submitting context.

        The bus is synchronous and "a subscriber's failure is not swallowed", so a course with
        no credit weight fails the submission rather than silently dropping the transcript
        line. A grade recorded against units nobody could confirm is the CGPA being quietly
        wrong for four years.
        """
        await _seed_calendar(repos)
        await _seed_lecturer(repos)

        response = await client.post(
            f"{api}/faculty-department/grade-submissions",
            json={
                "lecturer_id": "lec-1",
                "session_id": "sess-2026",
                "student_id": "stu-1",
                "course_id": "csc101",
                "semester_id": "sem-1",
                "score": 78,
            },
        )
        assert response.status_code == 409
        assert response.json()["error"] == "CourseCreditsUnavailableError"

    async def test_a_lecturer_who_does_not_teach_the_course_is_forbidden(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """The one 403 in the system: the request is understood and the authority is missing."""
        await _seed_calendar(repos)
        await _seed_lecturer(repos, assigned_to="csc999")

        response = await client.post(
            f"{api}/faculty-department/grade-submissions",
            json={
                "lecturer_id": "lec-1",
                "session_id": "sess-2026",
                "student_id": "stu-1",
                "course_id": "csc101",
                "semester_id": "sem-1",
                "score": 78,
            },
        )
        assert response.status_code == 403
        assert response.json()["error"] == "LecturerNotAssignedToCourseError"

    async def test_a_closed_session_is_a_conflict(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_calendar(repos, open_session=False)
        await _seed_lecturer(repos)

        response = await client.post(
            f"{api}/faculty-department/grade-submissions",
            json={
                "lecturer_id": "lec-1",
                "session_id": "sess-2026",
                "student_id": "stu-1",
                "course_id": "csc101",
                "semester_id": "sem-1",
                "score": 78,
            },
        )
        assert response.status_code == 409
        assert response.json()["error"] == "SessionNotOpenError"

    async def test_an_unknown_lecturer_is_a_404(self, client: AsyncClient, api: str, repos) -> None:
        await _seed_calendar(repos)
        response = await client.post(
            f"{api}/faculty-department/grade-submissions",
            json={
                "lecturer_id": "nobody",
                "session_id": "sess-2026",
                "student_id": "stu-1",
                "course_id": "csc101",
                "semester_id": "sem-1",
                "score": 78,
            },
        )
        assert response.status_code == 404

    async def test_a_score_outside_the_scale_never_reaches_a_use_case(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        response = await client.post(
            f"{api}/faculty-department/grade-submissions",
            json={
                "lecturer_id": "lec-1",
                "session_id": "sess-2026",
                "student_id": "stu-1",
                "course_id": "csc101",
                "semester_id": "sem-1",
                "score": 101,
            },
        )
        assert response.status_code == 422
        assert response.json()["error"] == "RequestValidationError"


class TestReadingAPlacement:
    async def test_a_placement_joins_the_program_department_and_session(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        await _seed_calendar(repos)
        response = await client.get(
            f"{api}/faculty-department/programs/prog-csc/placement",
            params={"session_id": "sess-2026"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "program_id": "prog-csc",
            "department_id": "dept-csc",
            "department_code": "CSC",
            "faculty_id": "fac-sci",
            "name": "BSc Computer Science",
            "code": "CSC",
            "is_admitting": False,
            "session_id": "sess-2026",
            "session_start_year": 2026,
            "session_label": "2026/2027",
            "session_is_open": True,
        }

    async def test_the_alphabetic_code_crosses_not_the_numeric_one(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """The four digits a matric number carries are Student Profile's translation, not this."""
        await _seed_calendar(repos)
        response = await client.get(
            f"{api}/faculty-department/programs/prog-csc/placement",
            params={"session_id": "sess-2026"},
        )
        assert response.json()["department_code"] == "CSC"

    async def test_an_unknown_program_is_a_404(self, client: AsyncClient, api: str, repos) -> None:
        await _seed_calendar(repos)
        response = await client.get(
            f"{api}/faculty-department/programs/nope/placement",
            params={"session_id": "sess-2026"},
        )
        assert response.status_code == 404

    async def test_a_missing_session_id_is_refused_by_the_framework(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.get(f"{api}/faculty-department/programs/prog-csc/placement")
        assert response.status_code == 422
