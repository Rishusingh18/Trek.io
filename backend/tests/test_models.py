"""
Database model metadata and constraint verification tests.
Mentions requirement IDs: FR-301, FR-501, FR-604, FR-701, FR-702, FR-801, FR-802, NFR-02, NFR-13.
"""
from app.db.models import (
    User,
    Course,
    Topic,
    ContentItem,
    Question,
    Attempt,
    MasteryScore,
    InteractionEvent,
    Recommendation,
    Experiment,
    Arm,
    ExperimentAssignment,
    Config,
    ConfigAudit,
    ClassTopicMasteryRollup,
    LearnerEngagementRollup,
    ExperimentMetricsRollup,
)


def test_models_composite_pk_fr301_mastery_score():
    """Verify FR-301: MasteryScore has composite primary key (user_id, topic_id)."""
    pk_columns = [col.name for col in MasteryScore.__table__.primary_key.columns]
    assert "user_id" in pk_columns
    assert "topic_id" in pk_columns
    assert len(pk_columns) == 2


def test_models_composite_pk_fr802_experiment_assignment():
    """Verify FR-802: ExperimentAssignment has composite primary key (user_id, experiment_id)."""
    pk_columns = [col.name for col in ExperimentAssignment.__table__.primary_key.columns]
    assert "user_id" in pk_columns
    assert "experiment_id" in pk_columns
    assert len(pk_columns) == 2


def test_models_partitioning_fr307_interaction_event():
    """Verify FR-307: InteractionEvent is partitioned by timestamp with composite PK."""
    pk_columns = [col.name for col in InteractionEvent.__table__.primary_key.columns]
    assert "event_id" in pk_columns
    assert "timestamp" in pk_columns
    dialect_options = InteractionEvent.__table__.dialect_options.get("postgresql", {})
    assert "partition_by" in dialect_options
    assert "RANGE (timestamp)" in dialect_options["partition_by"]


def test_models_indexes_fr604_attempt():
    """Verify FR-604: Attempt table has composite index on (user_id, answered_at)."""
    index_names = {idx.name for idx in Attempt.__table__.indexes}
    assert "ix_attempts_user_answered_at" in index_names
    idx = next(i for i in Attempt.__table__.indexes if i.name == "ix_attempts_user_answered_at")
    col_names = [col.name for col in idx.columns]
    assert col_names == ["user_id", "answered_at"]


def test_models_indexes_fr501_fr803_recommendation():
    """Verify FR-501 & FR-803: Recommendation table has indexes on (user_id, shown_at) and arm_id."""
    index_names = {idx.name for idx in Recommendation.__table__.indexes}
    assert "ix_recommendations_user_shown_at" in index_names
    assert "ix_recommendations_arm_id" in index_names

    user_shown_idx = next(i for i in Recommendation.__table__.indexes if i.name == "ix_recommendations_user_shown_at")
    assert [col.name for col in user_shown_idx.columns] == ["user_id", "shown_at"]


def test_models_rollups_nfr02_fr702_fr804():
    """Verify NFR-02, FR-702, FR-804: Rollup tables exist with proper primary keys."""
    # Class topic mastery rollup: composite PK (course_id, topic_id)
    class_pk = [col.name for col in ClassTopicMasteryRollup.__table__.primary_key.columns]
    assert class_pk == ["course_id", "topic_id"]

    # Learner engagement rollup: PK user_id
    learner_pk = [col.name for col in LearnerEngagementRollup.__table__.primary_key.columns]
    assert learner_pk == ["user_id"]

    # Experiment metrics rollup: composite PK (experiment_id, arm_id)
    exp_pk = [col.name for col in ExperimentMetricsRollup.__table__.primary_key.columns]
    assert exp_pk == ["experiment_id", "arm_id"]


def test_models_config_audit_nfr13():
    """Verify NFR-13: Config and ConfigAudit tables exist with expected schema."""
    config_cols = {col.name for col in Config.__table__.columns}
    assert {"key", "value", "description", "updated_at"}.issubset(config_cols)

    audit_cols = {col.name for col in ConfigAudit.__table__.columns}
    assert {"id", "key", "old_value", "new_value", "changed_by_user_id", "changed_at"}.issubset(audit_cols)
