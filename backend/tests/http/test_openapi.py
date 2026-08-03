"""The OpenAPI schema: that it generates, and that nothing leaked into it.

Phase 6.2's third verification criterion is "OpenAPI schema generated", which is a lower bar
than it sounds — a schema generates even when every route returns an untyped dict. So these
tests check the two things that make it worth generating: that every route declares what it
returns, and that no schema component is named after a domain type.

That last one is the *observable* form of "no route imports domain entities". The fitness test
checks the import graph; this checks the artifact. A route could in principle satisfy the
import rule and still hand FastAPI a response model built out of domain classes by some other
route, and the schema is where that would show up.
"""

import json

import pytest
from fastapi import FastAPI
from tests.http.conftest import api_routes

import main

DOMAIN_TYPE_NAMES = frozenset(
    {
        # aggregates and entities
        "Account",
        "AcademicRecord",
        "AdmissionCycle",
        "Applicant",
        "Course",
        "CourseOffering",
        "Department",
        "Enrollment",
        "Faculty",
        "Lecturer",
        "MatricSequence",
        "PaymentIntent",
        "Program",
        "Session",
        "Student",
        # value objects a careless response model would reach for
        "BioData",
        "Charge",
        "CourseFacts",
        "CourseGrade",
        "GradeCorrection",
        "MatricNumber",
        "Money",
        "Payment",
        "Term",
        "UtmeResult",
    }
)
"""Domain names that must not appear as schema components.

Listed rather than derived: deriving them by importing every context's ``domain/`` would make
this test's own imports the thing under suspicion. The response models are named ``*Response``
and ``*Schema`` throughout, so a collision here means a domain class was handed to FastAPI.
"""


@pytest.fixture
def schema(app: FastAPI) -> dict:
    return app.openapi()


def test_the_schema_generates(schema: dict) -> None:
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "University Management System"
    assert json.dumps(schema), "the schema must be JSON-serialisable to be served"


def test_every_context_mounted_a_router(schema: dict) -> None:
    tags = {tag for path in schema["paths"].values() for op in path.values() for tag in op["tags"]}
    assert tags == {
        "academic-records",
        "admissions",
        "billing",
        "course-catalog",
        "enrollment",
        "faculty-department",
        "meta",
        "student-profile",
    }


def test_every_route_is_versioned_except_the_probe(schema: dict) -> None:
    unversioned = [path for path in schema["paths"] if not path.startswith(main.API_PREFIX)]
    assert unversioned == ["/health"]


def test_the_route_walk_finds_them_all(app: FastAPI, schema: dict) -> None:
    """Guard: ``app.routes`` is not flat, and a walk that missed the routers would pass below."""
    assert len(api_routes(app)) == sum(len(methods) for methods in schema["paths"].values())


def test_every_route_declares_a_response_model(app: FastAPI) -> None:
    """A route without one documents nothing and is free to change shape silently."""
    undeclared = [
        route.path
        for route in api_routes(app)
        if route.path != "/health" and route.response_model is None
    ]
    assert undeclared == []


def test_no_schema_component_is_named_after_a_domain_type(schema: dict) -> None:
    components = set(schema.get("components", {}).get("schemas", {}))
    assert not components & DOMAIN_TYPE_NAMES, (
        "a domain type reached the wire; response models must be built from application views"
    )


def test_error_responses_are_documented(schema: dict) -> None:
    """A client generator that does not know a 409 is possible will not handle one."""
    register = schema["paths"][f"{main.API_PREFIX}/course-catalog/courses"]["post"]["responses"]
    assert "409" in register
    assert register["409"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "ErrorResponse"
    )


def test_the_outcome_unions_are_documented_as_unions(schema: dict) -> None:
    """A refused registration and an accepted one are both 200; the schema has to say so."""
    registration = schema["paths"][f"{main.API_PREFIX}/enrollment/registrations"]["post"]
    body = registration["responses"]["200"]["content"]["application/json"]["schema"]
    assert "anyOf" in body or "oneOf" in body


def test_the_webhook_declares_no_request_body(schema: dict) -> None:
    """It reads the raw bytes. A declared body model would mean the framework had parsed them."""
    webhook = schema["paths"][f"{main.API_PREFIX}/billing/webhooks/paystack"]["post"]
    assert "requestBody" not in webhook
