"""
Recommender entity models: Recommendation (SRS section 5.1, FR-501 to FR-505, FR-509, FR-803).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Recommendation(Base):
    """
    Recommended item served to a learner.
    Indexes: (user_id, shown_at) and arm_id.
    Traces to FR-501, FR-505, FR-803.
    """
    __tablename__ = "recommendations"

    rec_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    content_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.content_id", ondelete="CASCADE"), nullable=False
    )
    arm_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("arms.arm_id", ondelete="SET NULL"), nullable=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)  # Explainable one-line reason (FR-505, NFR-11)
    shown_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    outcome: Mapped[str] = mapped_column(String(50), default="ignored", nullable=False)  # accepted, dismissed, ignored

    __table_args__ = (
        Index("ix_recommendations_user_shown_at", "user_id", "shown_at"),
        Index("ix_recommendations_arm_id", "arm_id"),
    )
