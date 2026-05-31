"""add exam_slots table

Revision ID: a9ede2cf3577
Revises: ae9f4214d081
Create Date: 2026-05-30 11:22:35.278331+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a9ede2cf3577'
down_revision: Union[str, None] = 'ae9f4214d081'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('exam_slots',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('section_id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('date', sa.Date(), autoincrement=False, nullable=False),
    sa.Column('start_time', sa.String(length=5), autoincrement=False, nullable=False),
    sa.Column('duration_minutes', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('venue', sa.String(length=200), autoincrement=False, nullable=True),
    sa.Column('invigilator_id', sa.Integer(), autoincrement=False, nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['invigilator_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['section_id'], ['course_sections.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('section_id', 'date')
    )


def downgrade() -> None:
    op.drop_table('exam_slots')
