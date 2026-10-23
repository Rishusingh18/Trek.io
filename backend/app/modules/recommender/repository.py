"""
Recommender repository (FR-501 to FR-510, FR-803).
Only this file touches the recommendations table.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, update, func
from app.db.models.recommender import Recommendation


class RecommenderRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_recommendation(
        self,
        user_id: uuid.UUID,
        content_id: uuid.UUID,
        arm_id: Optional[uuid.UUID],
        rank: int,
        reason: str
    ) -> Recommendation:
        rec = Recommendation(
            rec_id=uuid.uuid4(),
            user_id=user_id,
            content_id=content_id,
            arm_id=arm_id,
            rank=rank,
            reason=reason,
            shown_at=datetime.now(timezone.utc),
            outcome="ignored"
        )
        self.db.add(rec)
        self.db.commit()
        self.db.refresh(rec)
        return rec

    def dismiss_recommendation(self, rec_id: uuid.UUID) -> Optional[Recommendation]:
        """FR-509: Mark recommendation as dismissed."""
        rec = self.db.execute(select(Recommendation).where(Recommendation.rec_id == rec_id)).scalar_one_or_none()
        if rec:
            rec.outcome = "dismissed"
            self.db.commit()
            self.db.refresh(rec)
        return rec

    def get_dismissed_content_ids(self, user_id: uuid.UUID, quiet_period_days: int = 7) -> List[uuid.UUID]:
        """FR-509: Dismissed items still in quiet period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=quiet_period_days)
        stmt = (
            select(Recommendation.content_id)
            .where(
                Recommendation.user_id == user_id,
                Recommendation.outcome == "dismissed",
                Recommendation.shown_at >= cutoff
            )
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_popular_content_ids(self, limit: int = 5) -> List[uuid.UUID]:
        """FR-510: Fallback to popular content items once enough completions/acceptances exist."""
        stmt = (
            select(Recommendation.content_id)
            .where(Recommendation.outcome.in_(["accepted", "ignored"]))
            .group_by(Recommendation.content_id)
            .order_by(func.count(Recommendation.rec_id).desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())


    def anonymize_learner_data(self, user_id: uuid.UUID, anonymous_id: uuid.UUID) -> None:
        """SRS section 5.3, NFR-07: Replace user_id with anonymous_id on recommendations."""
        from sqlalchemy import update
        self.db.execute(
            update(Recommendation).where(Recommendation.user_id == user_id).values(user_id=anonymous_id)
        )
        self.db.commit()
