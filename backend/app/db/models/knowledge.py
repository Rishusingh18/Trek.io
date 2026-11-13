"""
Knowledge model entities: Attempt, MasteryScore, InteractionEvent (SRS section 5.1, FR-301 to FR-307, FR-604).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, Boolean, Float, DateTime, ForeignKey, Index, PrimaryKeyConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Attempt(Base):
    """
    Learner's graded question attempt.
    Feeds MasteryScore updates (FR-302, FR-604).
    Index required: (user_id, answered_at).
    """
    __tablename__ = "attempts"

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # user_id is nullable for anonymization when a user requests data deletion (SRS 5.3)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.question_id", ondelete="CASCADE"), nullable=False
    )
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_taken: Mapped[float] = mapped_column(Float, nullable=False)  # in seconds
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    # Quiz session linkage (migration 0002). Nullable so legacy rows stay valid.
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    quiz_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # diagnostic | adaptive

    __table_args__ = (
        Index("ix_attempts_user_answered_at", "user_id", "answered_at"),
    )


class MasteryScore(Base):
    """
    Composite PK: (user_id, topic_id).
    Tracks mastery score (0 to 1) and confidence value per learner and topic.
    Traces to FR-301, FR-302, FR-306.
    """
    __tablename__ = "mastery_scores"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("topics.topic_id", ondelete="CASCADE"), primary_key=True
    )
    score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)  # m in [0, 1]
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # confidence in [0, 1]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class InteractionEvent(Base):
    """
    Append-only interaction event log partitioned by month (SRS 5.1, FR-307).
    Composite PK (event_id, timestamp) for Postgres RANGE partitioning.
    """
    __tablename__ = "interaction_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    # user_id is nullable to support anonymization requests (SRS 5.3)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    content_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # opened, completed, skipped, time_on_task, quiz_answered
    duration: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Quiz session linkage (migration 0002); set for quiz_answered events.
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    question_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("event_id", "timestamp"),
        Index("ix_interaction_events_user_timestamp", "user_id", "timestamp"),
        {
            "postgresql_partition_by": "RANGE (timestamp)"
        }
    )
