"""Add catalog columns the models expect but migration 0001 never created

Revision ID: 0003_catalog_columns
Revises: 0002_quiz_session_columns
Create Date: 2026-10-26

courses:        is_retired, instructor_id (FK users, SET NULL)   (FR-201)
topics:         is_retired                                       (FR-201, FR-202)
content_items:  is_retired, prerequisite_topic_ids               (FR-201, FR-202)
questions:      is_retired                                       (FR-201)
Retirement replaces deletion, so every column defaults to "not retired" for existing rows.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0003_catalog_columns'
down_revision: Union[str, None] = '0002_quiz_session_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_retired() -> sa.Column:
    return sa.Column('is_retired', sa.Boolean(), nullable=False, server_default=sa.false())


def upgrade() -> None:
    for table in ('courses', 'topics', 'content_items', 'questions'):
        op.add_column(table, _is_retired())

    op.add_column('courses', sa.Column('instructor_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_courses_instructor_id_users', 'courses', 'users',
                          ['instructor_id'], ['user_id'], ondelete='SET NULL')
    op.create_index('ix_courses_instructor_id', 'courses', ['instructor_id'])

    op.add_column('content_items', sa.Column(
        'prerequisite_topic_ids', postgresql.JSONB(astext_type=sa.Text()),
        nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('content_items', 'prerequisite_topic_ids')
    op.drop_index('ix_courses_instructor_id', table_name='courses')
    op.drop_constraint('fk_courses_instructor_id_users', 'courses', type_='foreignkey')
    op.drop_column('courses', 'instructor_id')
    for table in ('questions', 'content_items', 'topics', 'courses'):
        op.drop_column(table, 'is_retired')
