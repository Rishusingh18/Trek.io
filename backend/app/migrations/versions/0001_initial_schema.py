"""Initial schema migration with all core entities, partitioned events, and rollups

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-22

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users table (FR-101, FR-102, FR-104)
    op.create_table(
        'users',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='learner'),
        sa.Column('consent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. Courses table (FR-201)
    op.create_table(
        'courses',
        sa.Column('course_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # 3. Topics table (FR-201, FR-202)
    op.create_table(
        'topics',
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('course_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('courses.course_id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('prerequisite_topic_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_topics_course_id', 'topics', ['course_id'])

    # 4. ContentItems table (FR-201, FR-202)
    op.create_table(
        'content_items',
        sa.Column('content_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('topics.topic_id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('difficulty', sa.Integer(), nullable=False),
        sa.Column('duration', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_content_items_topic_id', 'content_items', ['topic_id'])

    # 5. Questions table (FR-201, FR-602)
    op.create_table(
        'questions',
        sa.Column('question_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('topics.topic_id', ondelete='CASCADE'), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('difficulty', sa.Float(), nullable=False),
        sa.Column('correct_answer', sa.String(length=255), nullable=False),
        sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_questions_topic_id', 'questions', ['topic_id'])

    # 6. Attempts table (FR-604) - Indexed by (user_id, answered_at)
    op.create_table(
        'attempts',
        sa.Column('attempt_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('question_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('questions.question_id', ondelete='CASCADE'), nullable=False),
        sa.Column('correct', sa.Boolean(), nullable=False),
        sa.Column('time_taken', sa.Float(), nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_attempts_user_answered_at', 'attempts', ['user_id', 'answered_at'])

    # 7. MasteryScore table (FR-301) - Composite PK: (user_id, topic_id)
    op.create_table(
        'mastery_scores',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('topics.topic_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # 8. InteractionEvents table (FR-307) - Append-only partitioned by month
    op.execute("""
        CREATE TABLE interaction_events (
            event_id UUID NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
            user_id UUID,
            content_id UUID,
            event_type VARCHAR(50) NOT NULL,
            duration DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            PRIMARY KEY (event_id, timestamp)
        ) PARTITION BY RANGE (timestamp);
    """)
    op.execute("CREATE INDEX ix_interaction_events_user_timestamp ON interaction_events (user_id, timestamp);")

    # Create monthly partitions for default operational window
    for year in (2026, 2027):
        for month in range(1, 13):
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            from_date = f"{year:04d}-{month:02d}-01"
            to_date = f"{next_year:04d}-{next_month:02d}-01"
            partition_name = f"interaction_events_y{year}m{month:02d}"
            op.execute(f"""
                CREATE TABLE IF NOT EXISTS {partition_name} PARTITION OF interaction_events
                FOR VALUES FROM ('{from_date}') TO ('{to_date}');
            """)

    # 9. Experiments table (FR-801)
    op.create_table(
        'experiments',
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('primary_metric', sa.String(length=100), nullable=False, server_default='post_test_gain'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # 10. Arms table (FR-801)
    op.create_table(
        'arms',
        sa.Column('arm_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('experiments.experiment_id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('strategy', sa.String(length=50), nullable=False),
        sa.Column('parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('allocation_share', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_arms_experiment_id', 'arms', ['experiment_id'])

    # 11. ExperimentAssignments table (FR-802) - Composite PK: (user_id, experiment_id)
    op.create_table(
        'experiment_assignments',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('experiments.experiment_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('arm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('arms.arm_id', ondelete='CASCADE'), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # 12. Recommendations table (FR-501 to FR-505, FR-803) - Indexed by (user_id, shown_at) and arm_id
    op.create_table(
        'recommendations',
        sa.Column('rec_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('content_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('content_items.content_id', ondelete='CASCADE'), nullable=False),
        sa.Column('arm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('arms.arm_id', ondelete='SET NULL'), nullable=True),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('shown_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('outcome', sa.String(length=50), nullable=False, server_default='ignored'),
    )
    op.create_index('ix_recommendations_user_shown_at', 'recommendations', ['user_id', 'shown_at'])
    op.create_index('ix_recommendations_arm_id', 'recommendations', ['arm_id'])

    # 13. Config & ConfigAudit tables (NFR-13, FR-807)
    op.create_table(
        'configs',
        sa.Column('key', sa.String(length=100), primary_key=True),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    op.create_table(
        'config_audits',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('old_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('changed_by_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_config_audits_key', 'config_audits', ['key'])

    # 14. Rollup tables (NFR-02, FR-701, FR-702, FR-804)
    # Class topic mastery rollup: composite PK (course_id, topic_id)
    op.create_table(
        'class_topic_mastery_rollups',
        sa.Column('course_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('courses.course_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('topic_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('topics.topic_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('average_mastery', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('learner_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('weak_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Learner engagement rollup: PK user_id
    op.create_table(
        'learner_engagement_rollups',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('completion_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('skip_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('avg_session_time', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_events', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # Per-arm experiment metrics rollup: composite PK (experiment_id, arm_id)
    op.create_table(
        'experiment_metrics_rollups',
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('experiments.experiment_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('arm_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('arms.arm_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('acceptance_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('completion_rate_8w', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('post_test_gain', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('sample_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('guardrail_dropout_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('guardrail_abandonment_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('experiment_metrics_rollups')
    op.drop_table('learner_engagement_rollups')
    op.drop_table('class_topic_mastery_rollups')
    op.drop_index('ix_config_audits_key', table_name='config_audits')
    op.drop_table('config_audits')
    op.drop_table('configs')
    op.drop_index('ix_recommendations_arm_id', table_name='recommendations')
    op.drop_index('ix_recommendations_user_shown_at', table_name='recommendations')
    op.drop_table('recommendations')
    op.drop_table('experiment_assignments')
    op.drop_index('ix_arms_experiment_id', table_name='arms')
    op.drop_table('arms')
    op.drop_table('experiments')
    op.execute("DROP TABLE IF EXISTS interaction_events CASCADE;")
    op.drop_table('mastery_scores')
    op.drop_index('ix_attempts_user_answered_at', table_name='attempts')
    op.drop_table('attempts')
    op.drop_index('ix_questions_topic_id', table_name='questions')
    op.drop_table('questions')
    op.drop_index('ix_content_items_topic_id', table_name='content_items')
    op.drop_table('content_items')
    op.drop_index('ix_topics_course_id', table_name='topics')
    op.drop_table('topics')
    op.drop_table('courses')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
