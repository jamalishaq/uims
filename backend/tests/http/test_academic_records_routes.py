"""Academic Records over HTTP: reading a record, and the one route that can change one.

Records are created by submitting grades, not by an HTTP call — there is no route that records
a grade, deliberately. So these tests build a record the only way a client can: through Faculty
& Department's submission route, over the bus, into this context.

Everything numeric crosses as a string. The CGPA is quantized to two places and the probation
threshold is judged on exactly that figure, so a float on the wire would put back the third
decimal place the domain removed on purpose.
"""

from httpx import AsyncClient
from tests.http.conftest import api_routes

from faculty_department.domain.department import Department
from faculty_department.domain.lecturer import Lecturer
from faculty_department.domain.program import Program
from faculty_department.domain.session import Semester, SemesterOrdinal, Session
from faculty_department.domain.values import AcademicYear


async def _seed_calendar_and_lecturer(repos, courses: tuple[str, ...]) -> None:
    await repos.departments().add(
        Department(
            department_id="dept-csc", faculty_id="fac-sci", name="Computer Science", code="CSC"
        )
    )
    await repos.programs().add(
        Program.create(program_id="prog-csc", department_id="dept-csc", name="BSc CS", code="CSC")
    )
    session = Session.plan(
        session_id="sess-2026",
        academic_year=AcademicYear(2026),
        semesters=[
            Semester("sem-1", SemesterOrdinal.FIRST),
            Semester("sem-2", SemesterOrdinal.SECOND),
        ],
    )
    session.open()
    await repos.sessions().add(session)

    lecturer = Lecturer(lecturer_id="lec-1", department_id="dept-csc", full_name="Ada Lovelace")
    for course_id in courses:
        lecturer.assign_to_course(course_id, "sess-2026")
    await repos.lecturers().add(lecturer)


async def _register_course(
    client: AsyncClient, api: str, course_id: str, *, credit_units: int
) -> None:
    response = await client.post(
        f"{api}/course-catalog/courses",
        json={
            "course_id": course_id,
            "department_id": "dept-csc",
            "code": course_id.upper(),
            "title": f"Course {course_id}",
            "credit_units": credit_units,
        },
    )
    assert response.status_code == 201, response.text


async def _submit(
    client: AsyncClient,
    api: str,
    as_lecturer,
    course_id: str,
    score: int,
    semester_id: str = "sem-1",
) -> None:
    """Submit a grade as ``lec-1``, who is the lecturer these fixtures assign to the course.

    The lecturer's own token, not the suite's university one: ``security.Lecturer`` admits no
    university fallback, because the domain check behind this route asks whether *this lecturer*
    teaches the course and a university principal could never satisfy it.
    """
    response = await client.post(
        f"{api}/faculty-department/grade-submissions",
        json={
            "lecturer_id": "lec-1",
            "session_id": "sess-2026",
            "student_id": "stu-1",
            "course_id": course_id,
            "semester_id": semester_id,
            "score": score,
        },
        headers=as_lecturer("lec-1"),
    )
    assert response.status_code == 201, response.text


class TestReadingARecord:
    async def test_a_student_with_no_record_is_a_404(self, client: AsyncClient, api: str) -> None:
        response = await client.get(f"{api}/academic-records/records/nobody")
        assert response.status_code == 404
        assert response.json()["error"] == "AcademicRecordNotFoundError"

    async def test_a_cgpa_is_weighted_by_the_credit_units_the_catalog_supplied(
        self, client: AsyncClient, api: str, as_lecturer, repos
    ) -> None:
        """A 3-unit A and a 1-unit F: (5.0*3 + 0.0*1) / 4 = 3.75, not the unweighted 2.5."""
        await _seed_calendar_and_lecturer(repos, ("csc101", "csc102"))
        await _register_course(client, api, "csc101", credit_units=3)
        await _register_course(client, api, "csc102", credit_units=1)
        await _submit(client, api, as_lecturer, "csc101", 78)
        await _submit(client, api, as_lecturer, "csc102", 20)

        body = (await client.get(f"{api}/academic-records/records/stu-1")).json()
        assert body["cgpa"] == "3.75"
        assert body["total_units"] == 4
        assert body["standing"] == "good standing"
        assert body["passed_course_ids"] == ["csc101"]

    async def test_a_cgpa_below_the_threshold_is_probation(
        self, client: AsyncClient, api: str, as_lecturer, repos
    ) -> None:
        """The confirmed threshold is 1.50, judged on the reported two-decimal figure."""
        await _seed_calendar_and_lecturer(repos, ("csc101",))
        await _register_course(client, api, "csc101", credit_units=3)
        await _submit(client, api, as_lecturer, "csc101", 45)

        body = (await client.get(f"{api}/academic-records/records/stu-1")).json()
        assert body["cgpa"] == "2.00"
        assert body["standing"] == "good standing"

    async def test_every_number_crosses_as_a_string(
        self, client: AsyncClient, api: str, as_lecturer, repos
    ) -> None:
        await _seed_calendar_and_lecturer(repos, ("csc101",))
        await _register_course(client, api, "csc101", credit_units=3)
        await _submit(client, api, as_lecturer, "csc101", 78)

        body = (await client.get(f"{api}/academic-records/records/stu-1")).json()
        assert isinstance(body["cgpa"], str)
        assert isinstance(body["grades"][0]["grade_point"], str)
        assert isinstance(body["grades"][0]["quality_points"], str)
        assert all(isinstance(gpa, str) for gpa in body["semester_gpas"].values())

    async def test_every_attempt_counts_and_none_is_replaced(
        self, client: AsyncClient, api: str, as_lecturer, repos
    ) -> None:
        """The confirmed carry-over rule: a course failed and later passed is two lines."""
        await _seed_calendar_and_lecturer(repos, ("csc101",))
        await _register_course(client, api, "csc101", credit_units=3)
        await _submit(client, api, as_lecturer, "csc101", 30, semester_id="sem-1")
        await _submit(client, api, as_lecturer, "csc101", 70, semester_id="sem-2")

        body = (await client.get(f"{api}/academic-records/records/stu-1")).json()
        assert len(body["grades"]) == 2, "both attempts stay on the transcript"
        assert body["total_units"] == 6, "and both count towards the CGPA"
        assert body["cgpa"] == "2.50"
        assert body["passed_course_ids"] == ["csc101"], "passed if any attempt passed"


class TestCorrectingAGrade:
    async def test_a_correction_changes_the_mark_and_leaves_an_audit_entry(
        self, client: AsyncClient, api: str, as_lecturer, repos
    ) -> None:
        await _seed_calendar_and_lecturer(repos, ("csc101",))
        await _register_course(client, api, "csc101", credit_units=3)
        await _submit(client, api, as_lecturer, "csc101", 45)

        response = await client.post(
            f"{api}/academic-records/records/stu-1/corrections",
            json={
                "course_id": "csc101",
                "semester_id": "sem-1",
                "corrected_score": 78,
                "reason": "script re-marked after appeal",
                "authorized_by": "registrar-1",
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["cgpa"] == "5.00"
        assert response.json()["correction"] == {
            "course_id": "csc101",
            "semester_id": "sem-1",
            "previous_score": 45,
            "corrected_score": 78,
            "reason": "script re-marked after appeal",
            "authorized_by": "registrar-1",
        }

        record = (await client.get(f"{api}/academic-records/records/stu-1")).json()
        assert len(record["corrections"]) == 1, (
            "the audit entry is on the record, not just the reply"
        )
        assert len(record["grades"]) == 1, "a correction amends the line; it does not add one"

    async def test_a_correction_without_a_reason_is_refused(
        self, client: AsyncClient, api: str
    ) -> None:
        """The reason and the authoriser are the entire audit trail."""
        response = await client.post(
            f"{api}/academic-records/records/stu-1/corrections",
            json={
                "course_id": "csc101",
                "semester_id": "sem-1",
                "corrected_score": 78,
                "reason": "",
                "authorized_by": "registrar-1",
            },
        )
        assert response.status_code == 422
        assert response.json()["error"] == "RequestValidationError"

    async def test_a_correction_to_a_grade_nobody_recorded_is_a_conflict(
        self, client: AsyncClient, api: str, as_lecturer, repos
    ) -> None:
        await _seed_calendar_and_lecturer(repos, ("csc101",))
        await _register_course(client, api, "csc101", credit_units=3)
        await _submit(client, api, as_lecturer, "csc101", 45)

        response = await client.post(
            f"{api}/academic-records/records/stu-1/corrections",
            json={
                "course_id": "csc999",
                "semester_id": "sem-1",
                "corrected_score": 78,
                "reason": "re-marked",
                "authorized_by": "registrar-1",
            },
        )
        assert response.status_code == 409
        assert response.json()["error"] == "GradeNotRecordedError"

    async def test_correcting_a_record_that_does_not_exist_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.post(
            f"{api}/academic-records/records/nobody/corrections",
            json={
                "course_id": "csc101",
                "semester_id": "sem-1",
                "corrected_score": 78,
                "reason": "re-marked",
                "authorized_by": "registrar-1",
            },
        )
        assert response.status_code == 404


def test_no_route_records_a_grade(app) -> None:
    """Recording stays on the bus, where the lecturer's assignment is checked first.

    An HTTP endpoint that recorded a grade would be a second way into a transcript that never
    asks whether the person submitting teaches the course.
    """
    paths = {route.path for route in api_routes(app)}
    assert not any(
        path.startswith("/api/v1/academic-records") and path.endswith("grades") for path in paths
    )
