"""add server default now to timestamp columns

Revision ID: 6b2a6f428747
Revises: 1a1d18c6d7e2
Create Date: 2026-05-30 12:13:17.689985+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b2a6f428747'
down_revision: Union[str, None] = '1a1d18c6d7e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = [
    "academic_sessions", "allocations", "applications", "assignments",
    "attendance_records", "books", "borrowings", "course_enrollments",
    "course_sections", "courses", "departments", "exam_slots",
    "faculties", "fee_schedules", "hostels", "notifications",
    "payments", "programs", "rooms", "semesters", "staff",
    "students", "submissions", "theses", "users",
]


def upgrade() -> None:
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN created_at SET DEFAULT NOW()"
        )
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN updated_at SET DEFAULT NOW()"
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN created_at DROP DEFAULT"
        )
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN updated_at DROP DEFAULT"
        )
