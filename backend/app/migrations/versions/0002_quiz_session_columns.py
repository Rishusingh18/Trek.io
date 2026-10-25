"""Add quiz session linkage to attempts and interaction_events

Revision ID: 0002_quiz_session_columns
Revises: 0001_initial_schema
Create Date: 2026-10-26

All columns are nullable, so existing rows and the current quiz flow keep working.
ALTER TABLE ... ADD COLUMN on the partitioned interaction_events parent propagates to every partition.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0002_quiz_session_columns'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('attempts', sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('attempts', sa.Column('quiz_type', sa.String(length=20), nullable=True))
    op.create_index('ix_attempts_session_id', 'attempts', ['session_id'])
    op.add_column('interaction_events', sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('interaction_events', sa.Column('question_id', postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column('interaction_events', 'question_id')
    op.drop_column('interaction_events', 'session_id')
    op.drop_index('ix_attempts_session_id', table_name='attempts')
    op.drop_column('attempts', 'quiz_type')
    op.drop_column('attempts', 'session_id')
