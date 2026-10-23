"""
Experiments entity models: Experiment, Arm, ExperimentAssignment (SRS section 5.1, FR-801 to FR-803).
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class Experiment(Base, TimestampMixin):
    """
    A/B Experiment definition.
    Traces to FR-801, FR-806.
    """
    __tablename__ = "experiments"

    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    primary_metric: Mapped[str] = mapped_column(String(100), default="post_test_gain", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)  # draft, active, paused, completed
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    arms: Mapped[List["Arm"]] = relationship("Arm", back_populates="experiment", cascade="all, delete-orphan")


class Arm(Base):
    """
    Experiment variant/arm tied to a strategy and configuration parameters.
    Traces to FR-801.
    """
    __tablename__ = "arms"

    arm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiments.experiment_id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy: Mapped[str] = mapped_column(String(50), nullable=False)  # rules, embeddings, collaborative
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    allocation_share: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="arms")


class ExperimentAssignment(Base):
    """
    Persistent assignment fixing a learner to one arm for an experiment.
    Composite PK: (user_id, experiment_id).
    Traces to FR-802.
    """
    __tablename__ = "experiment_assignments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("experiments.experiment_id", ondelete="CASCADE"), primary_key=True
    )
    arm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("arms.arm_id", ondelete="CASCADE"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
