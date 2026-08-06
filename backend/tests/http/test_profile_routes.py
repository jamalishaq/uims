"""Staff and student profiles over HTTP.

Two surfaces that had almost nothing. Faculty & Department could create a lecturer and then do
nothing with them — including assign a course, which is the thing ``SubmitGrade`` authorizes
against, so the grade-submission route was unreachable for anyone not seeded by hand. Student
Profile could create a student and never show one, so the matric number it issued went
nowhere.

The student surface stays deliberately thin: a portal composes a student's page from four
contexts, and a read here that assembled it would be one module knowing all four.
"""

from httpx import AsyncClient

FACULTY = {"faculty_id": "fac-sci", "name": "Science", "code": "SCI"}
DEPARTMENT = {
    "department_id": "dept-csc",
    "faculty_id": "fac-sci",
    "name": "Computer Science",
    "code": "CSC",
}
PROGRAM = {
    "program_id": "prog-csc",
    "department_id": "dept-csc",
    "name": "BSc Computer Science",
    "code": "CSC",
}
LECTURER = {
    "lecturer_id": "lec-1",
    "department_id": "dept-csc",
    "full_name": "Dr Adaeze Okonkwo",
}
PHD = {
    "degree": "PhD",
    "discipline": "Computer Science",
    "institution": "University of Ibadan",
    "year": 2014,
}
MSC = {
    "degree": "M.Sc",
    "discipline": "Computer Science",
    "institution": "University of Lagos",
    "year": 2009,
}

PLANNED_SESSION = {
    "session_id": "sess-2026",
    "academic_year": 2026,
    "semesters": [
        {"semester_id": "sem-1", "ordinal": 1},
        {"semester_id": "sem-2", "ordinal": 2},
    ],
}

STUDENT = {
    "student_id": "stu-1",
    "program_id": "prog-csc",
    "entry_session_id": "sess-2026",
    "full_name": "Chidi Nwosu",
    "email": "chidi@example.com",
}


async def _a_lecturer(client: AsyncClient, api: str) -> None:
    await client.post(f"{api}/faculty-department/faculties", json=FACULTY)
    await client.post(f"{api}/faculty-department/departments", json=DEPARTMENT)
    await client.post(f"{api}/faculty-department/lecturers", json=LECTURER)


async def _a_placement(client: AsyncClient, api: str) -> None:
    """Everything ``RegisterNewStudent`` needs to compose a matric number.

    The department code register is configuration with no default, and ``dept-csc``'s ``CSC``
    is the one entry ``tests/http/conftest.py`` supplies — so the placement has to resolve to
    *that* department or no number can be issued.
    """
    await client.post(f"{api}/faculty-department/faculties", json=FACULTY)
    await client.post(f"{api}/faculty-department/departments", json=DEPARTMENT)
    await client.post(f"{api}/faculty-department/programs", json=PROGRAM)
    await client.post(f"{api}/faculty-department/sessions", json=PLANNED_SESSION)
    await client.post(f"{api}/faculty-department/sessions/sess-2026/opening")


class TestTheStaffRecord:
    async def test_a_new_lecturer_has_nothing_on_file(self, client: AsyncClient, api: str) -> None:
        """``null`` says nobody has recorded it — a default would say something untrue."""
        await _a_lecturer(client, api)

        body = (await client.get(f"{api}/faculty-department/lecturers/lec-1")).json()

        assert body["rank"] is None
        assert body["employment_status"] is None
        assert body["qualifications"] == []

    async def test_the_record_can_be_filled_in(self, client: AsyncClient, api: str) -> None:
        await _a_lecturer(client, api)

        response = await client.put(
            f"{api}/faculty-department/lecturers/lec-1/profile",
            json={
                "rank": "senior lecturer",
                "employment_status": "full-time",
                "qualifications": [MSC, PHD],
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["rank"] == "senior lecturer"
        assert body["employment_status"] == "full-time"
        assert [held["degree"] for held in body["qualifications"]] == ["M.Sc", "PhD"]

    async def test_amending_replaces_rather_than_patches(
        self, client: AsyncClient, api: str
    ) -> None:
        """Omitted fields clear, because this is a form being saved."""
        await _a_lecturer(client, api)
        url = f"{api}/faculty-department/lecturers/lec-1/profile"
        await client.put(url, json={"rank": "professor", "qualifications": [PHD]})

        body = (await client.put(url, json={"employment_status": "sabbatical"})).json()

        assert body["rank"] is None
        assert body["qualifications"] == []
        assert body["employment_status"] == "sabbatical"

    async def test_a_rank_this_university_does_not_have_is_a_422(
        self, client: AsyncClient, api: str
    ) -> None:
        """Not silently dropped: a discarded rank reads the same as one nobody filled in."""
        await _a_lecturer(client, api)

        response = await client.put(
            f"{api}/faculty-department/lecturers/lec-1/profile",
            json={"rank": "grand vizier"},
        )
        assert response.status_code == 422
        assert response.json()["error"] == "InvalidRankError"

    async def test_a_degree_awarded_in_the_future_is_a_422(
        self, client: AsyncClient, api: str
    ) -> None:
        await _a_lecturer(client, api)

        response = await client.put(
            f"{api}/faculty-department/lecturers/lec-1/profile",
            json={"qualifications": [PHD | {"year": 3000}]},
        )
        assert response.status_code == 422
        assert response.json()["error"] == "InvalidQualificationError"

    async def test_a_lecturer_nobody_has_is_a_404(self, client: AsyncClient, api: str) -> None:
        response = await client.get(f"{api}/faculty-department/lecturers/nobody")
        assert response.status_code == 404


class TestCourseAssignments:
    async def test_assigning_a_course_makes_grade_submission_reachable(
        self, client: AsyncClient, api: str, as_lecturer, repos
    ) -> None:
        """The whole reason assignments matter: ``SubmitGrade`` authorizes against exactly this.

        Before this route existed a lecturer created through the API taught nothing forever,
        so the grade route answered 403 to everybody.
        """
        await _a_placement(client, api)
        await client.post(f"{api}/faculty-department/lecturers", json=LECTURER)
        await client.post(
            f"{api}/course-catalog/courses",
            json={
                "course_id": "CSC101",
                "department_id": "dept-csc",
                "code": "CSC101",
                "title": "Intro to Computing",
                "credit_units": 3,
            },
        )

        assigned = await client.put(
            f"{api}/faculty-department/lecturers/lec-1/courses/CSC101",
            json={"session_id": "sess-2026"},
        )
        graded = await client.post(
            f"{api}/faculty-department/grade-submissions",
            json={
                "lecturer_id": "lec-1",
                "session_id": "sess-2026",
                "student_id": "stu-1",
                "course_id": "CSC101",
                "semester_id": "sem-1",
                "score": 68,
            },
            headers=as_lecturer("lec-1"),
        )

        assert assigned.status_code == 201, assigned.text
        assert graded.status_code == 201, graded.text

    async def test_the_assignment_is_reported_on_the_lecturer(
        self, client: AsyncClient, api: str
    ) -> None:
        await _a_lecturer(client, api)

        response = await client.put(
            f"{api}/faculty-department/lecturers/lec-1/courses/CSC101",
            json={"session_id": "sess-2026"},
        )

        assert response.status_code == 201, response.text
        assert response.json()["assignments"] == [
            {"course_id": "CSC101", "session_id": "sess-2026"}
        ]

    async def test_assigning_the_same_course_twice_in_a_session_is_a_409(
        self, client: AsyncClient, api: str
    ) -> None:
        await _a_lecturer(client, api)
        url = f"{api}/faculty-department/lecturers/lec-1/courses/CSC101"
        await client.put(url, json={"session_id": "sess-2026"})

        response = await client.put(url, json={"session_id": "sess-2026"})
        assert response.status_code == 409

    async def test_the_same_course_in_another_session_is_a_separate_assignment(
        self, client: AsyncClient, api: str
    ) -> None:
        """Teaching CSC101 in 2026/2027 says nothing about 2027/2028."""
        await _a_lecturer(client, api)
        url = f"{api}/faculty-department/lecturers/lec-1/courses/CSC101"
        await client.put(url, json={"session_id": "sess-2026"})

        response = await client.put(url, json={"session_id": "sess-2027"})
        assert response.status_code == 201
        assert len(response.json()["assignments"]) == 2

    async def test_withdrawing_removes_only_that_session(
        self, client: AsyncClient, api: str
    ) -> None:
        await _a_lecturer(client, api)
        url = f"{api}/faculty-department/lecturers/lec-1/courses/CSC101"
        await client.put(url, json={"session_id": "sess-2026"})
        await client.put(url, json={"session_id": "sess-2027"})

        response = await client.delete(url, params={"session_id": "sess-2026"})

        assert response.status_code == 200, response.text
        assert response.json()["assignments"] == [
            {"course_id": "CSC101", "session_id": "sess-2027"}
        ]

    async def test_withdrawing_from_a_course_they_do_not_teach_is_a_403(
        self, client: AsyncClient, api: str
    ) -> None:
        await _a_lecturer(client, api)

        response = await client.delete(
            f"{api}/faculty-department/lecturers/lec-1/courses/CSC101",
            params={"session_id": "sess-2026"},
        )
        assert response.status_code == 403


class TestListingADepartmentsStaff:
    async def test_it_lists_the_department(self, client: AsyncClient, api: str) -> None:
        await _a_lecturer(client, api)
        await client.post(
            f"{api}/faculty-department/lecturers",
            json=LECTURER | {"lecturer_id": "lec-2", "full_name": "Dr Bola Adeyemi"},
        )

        response = await client.get(f"{api}/faculty-department/departments/dept-csc/lecturers")

        assert response.status_code == 200, response.text
        assert {one["lecturer_id"] for one in response.json()["lecturers"]} == {"lec-1", "lec-2"}

    async def test_a_department_nobody_has_lists_empty(self, client: AsyncClient, api: str) -> None:
        response = await client.get(f"{api}/faculty-department/departments/dept-nobody/lecturers")
        assert response.status_code == 200
        assert response.json()["lecturers"] == []


class TestTheStudentSurface:
    async def test_a_registered_student_can_be_read_back(
        self, client: AsyncClient, api: str, repos
    ) -> None:
        """The matric number issued at registration had nowhere to be shown before this."""
        await _a_placement(client, api)
        created = await client.post(f"{api}/student-profile/students", json=STUDENT)
        assert created.status_code == 201, created.text

        response = await client.get(f"{api}/student-profile/students/stu-1")

        assert response.status_code == 200, response.text
        assert response.json()["matric_number"] == created.json()["matric_number"]

    async def test_a_student_can_be_found_by_matric_number(
        self, client: AsyncClient, api: str
    ) -> None:
        await _a_placement(client, api)
        created = await client.post(f"{api}/student-profile/students", json=STUDENT)
        matric_number = created.json()["matric_number"]

        response = await client.get(
            f"{api}/student-profile/students", params={"matric_number": matric_number}
        )

        assert response.status_code == 200, response.text
        assert response.json()["student_id"] == "stu-1"

    async def test_a_student_can_be_found_by_applicant_id(
        self, client: AsyncClient, api: str
    ) -> None:
        """How a client follows a matriculation: nothing is published back to Admissions."""
        await _a_placement(client, api)
        await client.post(
            f"{api}/student-profile/students", json=STUDENT | {"applicant_id": "app-1"}
        )

        response = await client.get(
            f"{api}/student-profile/students", params={"applicant_id": "app-1"}
        )

        assert response.status_code == 200, response.text
        assert response.json()["student_id"] == "stu-1"

    async def test_a_matric_number_nobody_could_hold_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        """Somebody typed into a lookup box; "no student with that number" is the honest answer."""
        response = await client.get(
            f"{api}/student-profile/students", params={"matric_number": "not-a-number"}
        )
        assert response.status_code == 404

    async def test_giving_both_identifiers_is_a_422(self, client: AsyncClient, api: str) -> None:
        response = await client.get(
            f"{api}/student-profile/students",
            params={"matric_number": "260591001", "applicant_id": "app-1"},
        )
        assert response.status_code == 422

    async def test_a_misspelled_name_can_be_corrected(self, client: AsyncClient, api: str) -> None:
        await _a_placement(client, api)
        created = await client.post(
            f"{api}/student-profile/students", json=STUDENT | {"full_name": "Chidi Nwoso"}
        )
        matric_number = created.json()["matric_number"]

        response = await client.put(
            f"{api}/student-profile/students/stu-1/bio-data",
            json={"full_name": "Chidi Nwosu", "email": "chidi@example.com"},
        )

        assert response.status_code == 200, response.text
        assert response.json()["full_name"] == "Chidi Nwosu"
        assert response.json()["matric_number"] == matric_number, "the number does not move"

    async def test_correcting_a_student_nobody_has_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.put(
            f"{api}/student-profile/students/nobody/bio-data", json={"full_name": "Nobody"}
        )
        assert response.status_code == 404
        assert response.json()["error"] == "StudentNotFoundError"
