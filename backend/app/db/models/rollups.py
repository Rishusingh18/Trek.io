"""
Rollup tables for fast dashboard and experiment reads (NFR-02, FR-701, FR-702, FR-804).
Precomputed asynchronously by the worker process.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ClassTopicMasteryRollup(Base):
    """
    Class topic mastery rollup for instructor dashboard (FR-702, NFR-02).
    Composite PK: (course_id, topic_id).
    """
    __tablename__ = "class_topic_mastery_rollups"

    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.course_id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.topic_id", ondelete="CASCADE"), primary_key=True
    )
    average_mastery: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    learner_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    weak_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class LearnerEngagementRollup(Base):
    """
    Per-learner completion rate, skip rate, and average session time (FR-307, FR-701).
    PK: user_id.
    """
    __tablename__ = "learner_engagement_rollups"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    completion_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    skip_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_session_time: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # in seconds
    total_events: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class ExperimentMetricsRollup(Base):
    """
    Per-arm metrics and guardrails for A/B experiments (FR-804, FR-805, FR-806).
    Composite PK: (experiment_id, arm_id).
    """
    __tablename__ = "experiment_metrics_rollups"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiments.experiment_id", ondelete="CASCADE"), primary_key=True
    )
    arm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("arms.arm_id", ondelete="CASCADE"), primary_key=True
    )
    acceptance_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completion_rate_8w: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    post_test_gain: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    guardrail_dropout_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    guardrail_abandonment_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
