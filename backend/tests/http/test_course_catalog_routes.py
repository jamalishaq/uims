"""Course Catalog over HTTP: the full CRUD surface, and every status its errors map to.

The context with the most routes, so it carries the most of the shared checking: that a route
returns the projection and not the aggregate, that a 404 and a 409 come from the right
refusals, and that the error envelope is the same shape whichever layer raised.
"""

import pytest
from httpx import AsyncClient


async def _register(client: AsyncClient, api: str, **overrides: object) -> dict:
    body = {
        "course_id": "csc101",
        "department_id": "dept-csc",
        "code": "CSC101",
        "title": "Introduction to Computer Science",
        "credit_units": 3,
    } | overrides
    response = await client.post(f"{api}/course-catalog/courses", json=body)
    assert response.status_code == 201, response.text
    return response.json()


class TestRegisteringACourse:
    async def test_a_registered_course_comes_back_as_primitives(
        self, client: AsyncClient, api: str
    ) -> None:
        """No ``Course`` crosses the wire: what arrives is the view, field for field."""
        body = await _register(client, api)
        assert body == {
            "course_id": "csc101",
            "department_id": "dept-csc",
            "code": "CSC101",
            "title": "Introduction to Computer Science",
            "credit_units": 3,
            "is_active": True,
            "prerequisite_ids": [],
        }

    async def test_a_repeated_course_id_is_a_conflict(self, client: AsyncClient, api: str) -> None:
        await _register(client, api)
        response = await client.post(
            f"{api}/course-catalog/courses",
            json={
                "course_id": "csc101",
                "department_id": "dept-csc",
                "code": "CSC102",
                "title": "Another",
                "credit_units": 3,
            },
        )
        assert response.status_code == 409

    async def test_a_repeated_code_is_a_conflict(self, client: AsyncClient, api: str) -> None:
        await _register(client, api)
        response = await client.post(
            f"{api}/course-catalog/courses",
            json={
                "course_id": "csc999",
                "department_id": "dept-csc",
                "code": "CSC101",
                "title": "Another",
                "credit_units": 3,
            },
        )
        assert response.status_code == 409
        assert response.json()["error"] == "DuplicateCourseCodeError"

    @pytest.mark.parametrize("credit_units", [0, -3])
    async def test_credit_units_that_are_not_a_number_of_credits_are_refused(
        self, client: AsyncClient, api: str, credit_units: int
    ) -> None:
        """Caught by the request model before a use case runs — hence the framework's 422."""
        response = await client.post(
            f"{api}/course-catalog/courses",
            json={
                "course_id": "csc101",
                "department_id": "dept-csc",
                "code": "CSC101",
                "title": "Introduction",
                "credit_units": credit_units,
            },
        )
        assert response.status_code == 422
        assert response.json()["error"] == "RequestValidationError"

    async def test_an_unknown_field_is_refused_rather_than_ignored(
        self, client: AsyncClient, api: str
    ) -> None:
        """``extra="forbid"``: a client sending ``credit_hours`` should hear about it."""
        response = await client.post(
            f"{api}/course-catalog/courses",
            json={
                "course_id": "csc101",
                "department_id": "dept-csc",
                "code": "CSC101",
                "title": "Introduction",
                "credit_units": 3,
                "credit_hours": 3,
            },
        )
        assert response.status_code == 422


class TestReadingACourse:
    async def test_a_course_can_be_read_back(self, client: AsyncClient, api: str) -> None:
        await _register(client, api)
        response = await client.get(f"{api}/course-catalog/courses/csc101")
        assert response.status_code == 200
        assert response.json()["code"] == "CSC101"

    async def test_a_course_nobody_registered_is_a_404(self, client: AsyncClient, api: str) -> None:
        response = await client.get(f"{api}/course-catalog/courses/nope")
        assert response.status_code == 404
        assert response.json() == {
            "error": "CourseNotFoundError",
            "detail": response.json()["detail"],
        }

    async def test_the_error_envelope_is_the_same_shape_as_the_frameworks(
        self, client: AsyncClient, api: str
    ) -> None:
        """A 404 from a route and a 404 from the router itself parse identically."""
        from_route = await client.get(f"{api}/course-catalog/courses/nope")
        from_framework = await client.get(f"{api}/course-catalog/no-such-path")
        assert from_framework.status_code == 404
        assert set(from_route.json()) == set(from_framework.json()) == {"error", "detail"}


class TestAmendingACourse:
    async def test_only_the_named_fields_change(self, client: AsyncClient, api: str) -> None:
        await _register(client, api)
        response = await client.patch(
            f"{api}/course-catalog/courses/csc101", json={"title": "Intro to CS"}
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Intro to CS"
        assert response.json()["credit_units"] == 3, "an omitted field is left alone"

    async def test_amending_a_course_nobody_registered_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        response = await client.patch(f"{api}/course-catalog/courses/nope", json={"title": "Intro"})
        assert response.status_code == 404


class TestRetirement:
    async def test_a_course_can_be_retired_and_reinstated(
        self, client: AsyncClient, api: str
    ) -> None:
        await _register(client, api)

        retired = await client.post(f"{api}/course-catalog/courses/csc101/retirement")
        assert retired.status_code == 200
        assert retired.json()["is_active"] is False

        reinstated = await client.delete(f"{api}/course-catalog/courses/csc101/retirement")
        assert reinstated.status_code == 200
        assert reinstated.json()["is_active"] is True

    async def test_a_retired_course_is_still_readable(self, client: AsyncClient, api: str) -> None:
        """Transcripts refer to courses no longer taught; retirement is not deletion."""
        await _register(client, api)
        await client.post(f"{api}/course-catalog/courses/csc101/retirement")

        response = await client.get(f"{api}/course-catalog/courses/csc101")
        assert response.status_code == 200
        assert response.json()["is_active"] is False


class TestPrerequisites:
    async def test_a_prerequisite_can_be_added_and_removed(
        self, client: AsyncClient, api: str
    ) -> None:
        await _register(client, api)
        await _register(client, api, course_id="csc201", code="CSC201", title="Data Structures")

        added = await client.put(f"{api}/course-catalog/courses/csc201/prerequisites/csc101")
        assert added.status_code == 200
        assert added.json()["prerequisite_ids"] == ["csc101"]

        removed = await client.delete(f"{api}/course-catalog/courses/csc201/prerequisites/csc101")
        assert removed.status_code == 200
        assert removed.json()["prerequisite_ids"] == []

    async def test_a_course_may_not_require_itself(self, client: AsyncClient, api: str) -> None:
        await _register(client, api)
        response = await client.put(f"{api}/course-catalog/courses/csc101/prerequisites/csc101")
        assert response.status_code == 409
        assert response.json()["error"] == "SelfPrerequisiteError"

    async def test_a_cycle_is_refused(self, client: AsyncClient, api: str) -> None:
        await _register(client, api)
        await _register(client, api, course_id="csc201", code="CSC201", title="Data Structures")
        await client.put(f"{api}/course-catalog/courses/csc201/prerequisites/csc101")

        response = await client.put(f"{api}/course-catalog/courses/csc101/prerequisites/csc201")
        assert response.status_code == 409
        assert response.json()["error"] == "PrerequisiteCycleError"

    async def test_a_prerequisite_that_does_not_exist_is_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        await _register(client, api)
        response = await client.put(f"{api}/course-catalog/courses/csc101/prerequisites/nope")
        assert response.status_code == 404
        assert response.json()["error"] == "PrerequisiteCourseNotFoundError"

    async def test_the_chain_is_transitive(self, client: AsyncClient, api: str) -> None:
        await _register(client, api)
        await _register(client, api, course_id="csc201", code="CSC201", title="Data Structures")
        await _register(client, api, course_id="csc301", code="CSC301", title="Algorithms")
        await client.put(f"{api}/course-catalog/courses/csc201/prerequisites/csc101")
        await client.put(f"{api}/course-catalog/courses/csc301/prerequisites/csc201")

        response = await client.get(f"{api}/course-catalog/courses/csc301/prerequisite-chain")
        assert response.status_code == 200
        assert set(response.json()["prerequisite_ids"]) == {"csc101", "csc201"}


class TestListingADepartment:
    async def test_retired_courses_are_excluded_unless_asked_for(
        self, client: AsyncClient, api: str
    ) -> None:
        await _register(client, api)
        await _register(client, api, course_id="csc201", code="CSC201", title="Data Structures")
        await client.post(f"{api}/course-catalog/courses/csc201/retirement")

        default = await client.get(f"{api}/course-catalog/departments/dept-csc/courses")
        assert [course["course_id"] for course in default.json()["courses"]] == ["csc101"]

        including = await client.get(
            f"{api}/course-catalog/departments/dept-csc/courses",
            params={"include_retired": True},
        )
        assert len(including.json()["courses"]) == 2

    async def test_a_department_nobody_has_is_an_empty_list_not_a_404(
        self, client: AsyncClient, api: str
    ) -> None:
        """``ListDepartmentCourses`` raises nothing, and the route does not invent a refusal."""
        response = await client.get(f"{api}/course-catalog/departments/nope/courses")
        assert response.status_code == 200
        assert response.json() == {"courses": []}
