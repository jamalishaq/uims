"""The registrar's dashboard over HTTP: capacity, cohort, and the policy on file.

The thing most worth testing here is not that the numbers are right but that the **two
populations stay separate**. ``offers_made`` counts places claimed on a program, including by
applicants who applied elsewhere and overflowed in through a fallback chain; the funnel counts
applicants who applied *to* the program, including ones placed somewhere else. They do not add
up, and a test that asserted they did would be encoding the confusion this read model exists to
prevent.

Everything is set up over HTTP, which is only possible because the write paths landed in the
same change.
"""

from httpx import AsyncClient

CSC = "prog-csc"
MTH = "prog-mth"
SESSION = "sess-2026"

SUBJECTS = [
    {"subject": "ENGLISH", "score": 70},
    {"subject": "MATHEMATICS", "score": 80},
    {"subject": "PHYSICS", "score": 75},
    {"subject": "CHEMISTRY", "score": 65},
]


def an_application(applicant_id: str, program_id: str = CSC) -> dict:
    return {
        "applicant_id": applicant_id,
        "program_id": program_id,
        "session_id": SESSION,
        "full_name": f"Applicant {applicant_id}",
        "utme_scores": SUBJECTS,
    }


async def _seed_faculty_structure(client: AsyncClient, api: str) -> None:
    """Two programs in one department, both admitting, in an open session."""
    await client.post(
        f"{api}/faculty-department/faculties",
        json={"faculty_id": "fac-sci", "name": "Science", "code": "SCI"},
    )
    await client.post(
        f"{api}/faculty-department/departments",
        json={
            "department_id": "dept-csc",
            "faculty_id": "fac-sci",
            "name": "Computer Science",
            "code": "CSC",
        },
    )
    for program_id, name, code in ((CSC, "BSc Computer Science", "CSC"), (MTH, "BSc Maths", "MTH")):
        await client.post(
            f"{api}/faculty-department/programs",
            json={
                "program_id": program_id,
                "department_id": "dept-csc",
                "name": name,
                "code": code,
            },
        )
        await client.put(
            f"{api}/faculty-department/programs/{program_id}/admissions",
            json={"is_admitting": True},
        )
    await client.post(
        f"{api}/faculty-department/sessions",
        json={
            "session_id": SESSION,
            "academic_year": 2026,
            "semesters": [
                {"semester_id": "sem-1", "ordinal": 1},
                {"semester_id": "sem-2", "ordinal": 2},
            ],
        },
    )
    await client.post(f"{api}/faculty-department/sessions/{SESSION}/opening")


async def _seed_admissions_policy(client: AsyncClient, api: str, csc_quota: int = 1) -> None:
    for program_id in (CSC, MTH):
        await client.post(
            f"{api}/admissions/entry-requirements",
            json={
                "program_id": program_id,
                "session_id": SESSION,
                "required_subjects": ["ENGLISH", "MATHEMATICS"],
            },
        )
    await client.post(
        f"{api}/admissions/admission-cycles",
        json={"program_id": CSC, "session_id": SESSION, "quota": csc_quota},
    )
    await client.post(
        f"{api}/admissions/admission-cycles",
        json={"program_id": MTH, "session_id": SESSION, "quota": 5},
    )
    await client.post(
        f"{api}/admissions/alternative-policies",
        json={"program_id": CSC, "session_id": SESSION, "alternatives": [MTH]},
    )


class TestTheDashboard:
    async def test_an_untouched_program_summarises_to_zeroes(
        self, client: AsyncClient, api: str
    ) -> None:
        """Never a 404: "nothing has happened yet" is a truthful answer, and nulls say the
        quota has not been set rather than that it is zero."""
        response = await client.get(
            f"{api}/admissions/programs/{CSC}/admissions-summary", params={"session_id": SESSION}
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["quota"] is None
        assert body["is_full"] is None
        assert body["total_applicants"] == 0

    async def test_the_funnel_reports_each_status_separately(
        self, client: AsyncClient, api: str
    ) -> None:
        """One "applicants" figure would hide the screened-and-waiting, which is the work."""
        await _seed_faculty_structure(client, api)
        await _seed_admissions_policy(client, api, csc_quota=5)
        for applicant_id in ("app-1", "app-2", "app-3"):
            await client.post(f"{api}/admissions/applications", json=an_application(applicant_id))
        await client.post(f"{api}/admissions/applicants/app-2/screening")
        await client.post(f"{api}/admissions/applicants/app-3/screening")
        await client.post(f"{api}/admissions/applicants/app-3/offer")

        body = (
            await client.get(
                f"{api}/admissions/programs/{CSC}/admissions-summary",
                params={"session_id": SESSION},
            )
        ).json()

        assert (body["applied"], body["screened"], body["offered"]) == (1, 1, 1)
        assert body["total_applicants"] == 3

    async def test_capacity_and_cohort_are_different_populations(
        self, client: AsyncClient, api: str
    ) -> None:
        """Computer Science holds one place and overflows into Mathematics.

        Two applicants apply to CSC. The first takes its only place; the second is pushed down
        the chain onto Mathematics. Afterwards **Mathematics has an offer made against a cohort
        of nobody** — the applicant it seated applied to Computer Science — which is exactly
        the pair of numbers a registrar must not read as one.
        """
        await _seed_faculty_structure(client, api)
        await _seed_admissions_policy(client, api, csc_quota=1)
        for applicant_id in ("app-1", "app-2"):
            await client.post(f"{api}/admissions/applications", json=an_application(applicant_id))
            await client.post(f"{api}/admissions/applicants/{applicant_id}/screening")
            await client.post(f"{api}/admissions/applicants/{applicant_id}/offer")

        csc = (
            await client.get(
                f"{api}/admissions/programs/{CSC}/admissions-summary",
                params={"session_id": SESSION},
            )
        ).json()
        mth = (
            await client.get(
                f"{api}/admissions/programs/{MTH}/admissions-summary",
                params={"session_id": SESSION},
            )
        ).json()

        assert (csc["offers_made"], csc["is_full"], csc["total_applicants"]) == (1, True, 2)
        assert csc["offered"] == 2, "both applied to CSC and both hold an offer"
        assert mth["offers_made"] == 1, "one place on Maths went to a CSC applicant"
        assert mth["total_applicants"] == 0, "nobody applied to Maths"


class TestTheWorkingList:
    async def test_it_lists_everyone_who_applied_to_the_program(
        self, client: AsyncClient, api: str
    ) -> None:
        await _seed_faculty_structure(client, api)
        await _seed_admissions_policy(client, api, csc_quota=5)
        for applicant_id in ("app-1", "app-2"):
            await client.post(f"{api}/admissions/applications", json=an_application(applicant_id))

        response = await client.get(
            f"{api}/admissions/programs/{CSC}/applicants", params={"session_id": SESSION}
        )

        assert response.status_code == 200, response.text
        assert {a["applicant_id"] for a in response.json()["applicants"]} == {"app-1", "app-2"}

    async def test_an_applicant_placed_elsewhere_stays_on_the_applied_list(
        self, client: AsyncClient, api: str
    ) -> None:
        """The reason the list is keyed on the applied program: a registrar's working list
        must not lose somebody the moment the offer flow places them elsewhere."""
        await _seed_faculty_structure(client, api)
        await _seed_admissions_policy(client, api, csc_quota=0)
        await client.post(f"{api}/admissions/applications", json=an_application("app-1"))
        await client.post(f"{api}/admissions/applicants/app-1/screening")
        await client.post(f"{api}/admissions/applicants/app-1/offer")

        csc = (
            await client.get(
                f"{api}/admissions/programs/{CSC}/applicants", params={"session_id": SESSION}
            )
        ).json()
        mth = (
            await client.get(
                f"{api}/admissions/programs/{MTH}/applicants", params={"session_id": SESSION}
            )
        ).json()

        (applicant,) = csc["applicants"]
        assert applicant["applied_program_id"] == CSC
        assert applicant["offered_program_id"] == MTH
        assert mth["applicants"] == [], "they never applied to Maths"

    async def test_the_status_filter_narrows_the_list(self, client: AsyncClient, api: str) -> None:
        await _seed_faculty_structure(client, api)
        await _seed_admissions_policy(client, api, csc_quota=5)
        for applicant_id in ("app-1", "app-2"):
            await client.post(f"{api}/admissions/applications", json=an_application(applicant_id))
        await client.post(f"{api}/admissions/applicants/app-2/screening")

        response = await client.get(
            f"{api}/admissions/programs/{CSC}/applicants",
            params={"session_id": SESSION, "status": "screened"},
        )

        assert [a["applicant_id"] for a in response.json()["applicants"]] == ["app-2"]

    async def test_an_unrecognised_status_is_a_422_rather_than_an_empty_list(
        self, client: AsyncClient, api: str
    ) -> None:
        """A typo answering the same as "no applicants" is one a registrar would act on."""
        response = await client.get(
            f"{api}/admissions/programs/{CSC}/applicants",
            params={"session_id": SESSION, "status": "shortlisted"},
        )
        assert response.status_code == 422

    async def test_the_session_is_required(self, client: AsyncClient, api: str) -> None:
        response = await client.get(f"{api}/admissions/programs/{CSC}/applicants")
        assert response.status_code == 422


class TestReadingThePolicyOnFile:
    async def test_the_cycle_comes_back_with_its_derived_figures(
        self, client: AsyncClient, api: str
    ) -> None:
        await _seed_faculty_structure(client, api)
        await _seed_admissions_policy(client, api, csc_quota=3)

        response = await client.get(
            f"{api}/admissions/programs/{CSC}/admission-cycle", params={"session_id": SESSION}
        )

        assert response.status_code == 200, response.text
        assert response.json()["places_remaining"] == 3

    async def test_a_cycle_nobody_opened_is_a_404(self, client: AsyncClient, api: str) -> None:
        response = await client.get(
            f"{api}/admissions/programs/{CSC}/admission-cycle", params={"session_id": SESSION}
        )
        assert response.status_code == 404

    async def test_the_entry_requirement_comes_back_sorted(
        self, client: AsyncClient, api: str
    ) -> None:
        await _seed_faculty_structure(client, api)
        await _seed_admissions_policy(client, api)

        response = await client.get(
            f"{api}/admissions/programs/{CSC}/entry-requirement", params={"session_id": SESSION}
        )

        assert response.status_code == 200, response.text
        assert response.json()["required_subjects"] == ["ENGLISH", "MATHEMATICS"]

    async def test_the_chain_comes_back_in_preference_order(
        self, client: AsyncClient, api: str
    ) -> None:
        await _seed_faculty_structure(client, api)
        await _seed_admissions_policy(client, api)

        response = await client.get(
            f"{api}/admissions/programs/{CSC}/alternative-policy", params={"session_id": SESSION}
        )

        assert response.status_code == 200, response.text
        assert response.json()["alternatives"] == [MTH]

    async def test_no_chain_published_is_a_404_rather_than_an_empty_one(
        self, client: AsyncClient, api: str
    ) -> None:
        """To the offer flow they are the same; to a registrar "nobody wrote one" and "we wrote
        one that says nowhere" are different states of the work."""
        response = await client.get(
            f"{api}/admissions/programs/{MTH}/alternative-policy", params={"session_id": SESSION}
        )
        assert response.status_code == 404
