"""
Knowledge repository (FR-301 to FR-307, FR-604).
Only this file touches attempts, mastery_scores, interaction_events, and learner_engagement_rollups.
Employs parameterized queries and SELECT ... FOR UPDATE on mastery rows.
"""
import uuid
import math
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func, update, delete
from app.db.models.knowledge import Attempt, MasteryScore, InteractionEvent
from app.db.models.content import ContentItem
from app.db.models.rollups import LearnerEngagementRollup


class KnowledgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_attempt(self, attempt_id: uuid.UUID) -> Optional[Attempt]:
        """NFR-08: Lookup attempt by client-generated ID for idempotency."""
        stmt = select(Attempt).where(Attempt.attempt_id == attempt_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def record_attempt(
        self,
        attempt_id: uuid.UUID,
        user_id: uuid.UUID,
        question_id: uuid.UUID,
        correct: bool,
        time_taken: float
    ) -> Attempt:
        """FR-604, NFR-08: Record attempt idempotently."""
        existing = self.get_attempt(attempt_id)
        if existing:
            return existing

        attempt = Attempt(
            attempt_id=attempt_id,
            user_id=user_id,
            question_id=question_id,
            correct=correct,
            time_taken=time_taken,
            answered_at=datetime.now(timezone.utc)
        )
        self.db.add(attempt)
        # Note: caller coordinates commit when running in multi-step atomic transaction
        return attempt

    def get_mastery(self, user_id: uuid.UUID, topic_id: uuid.UUID, for_update: bool = False) -> Optional[MasteryScore]:
        """FR-301, FR-302: Select with row lock (FOR UPDATE) to prevent concurrent overwrites."""
        stmt = select(MasteryScore).where(
            MasteryScore.user_id == user_id,
            MasteryScore.topic_id == topic_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def get_all_mastery_for_user(self, user_id: uuid.UUID) -> List[MasteryScore]:
        return list(self.db.execute(select(MasteryScore).where(MasteryScore.user_id == user_id)).scalars().all())

    def upsert_mastery(self, user_id: uuid.UUID, topic_id: uuid.UUID, score: float, confidence: float) -> MasteryScore:
        """Upsert mastery score and confidence under row lock."""
        mastery = self.get_mastery(user_id, topic_id, for_update=True)
        if mastery:
            mastery.score = score
            mastery.confidence = confidence
            mastery.updated_at = datetime.now(timezone.utc)
        else:
            mastery = MasteryScore(
                user_id=user_id,
                topic_id=topic_id,
                score=score,
                confidence=confidence,
                updated_at=datetime.now(timezone.utc)
            )
            self.db.add(mastery)
        return mastery

    def log_interaction_event(
        self,
        user_id: Optional[uuid.UUID],
        content_id: Optional[uuid.UUID],
        event_type: str,
        duration: float
    ) -> InteractionEvent:
        event = InteractionEvent(
            event_id=uuid.uuid4(),
            timestamp=datetime.now(timezone.utc),
            user_id=user_id,
            content_id=content_id,
            event_type=event_type,
            duration=duration
        )
        self.db.add(event)
        return event

    def derive_and_update_engagement_rollups(self, user_id: uuid.UUID) -> LearnerEngagementRollup:
        """
        FR-307: Derive per-learner completion rate, skip rate and average session time from events.
        Persist in learner_engagement_rollups table.
        """
        events = list(self.db.execute(
            select(InteractionEvent).where(InteractionEvent.user_id == user_id)
        ).scalars().all())

        total_events = len(events)
        if total_events == 0:
            rollup = LearnerEngagementRollup(
                user_id=user_id,
                completion_rate=0.0,
                skip_rate=0.0,
                avg_session_time=0.0,
                total_events=0,
                updated_at=datetime.now(timezone.utc)
            )
            return rollup

        completed_count = sum(1 for e in events if e.event_type == "completed")
        skipped_count = sum(1 for e in events if e.event_type == "skipped")
        denom = sum(1 for e in events if e.event_type in ("opened", "completed", "skipped"))
        if denom == 0:
            denom = total_events

        completion_rate = completed_count / denom
        skip_rate = skipped_count / denom

        durations = [e.duration for e in events if e.duration > 0]
        avg_session = (sum(durations) / len(durations)) if durations else 0.0

        existing = self.db.execute(
            select(LearnerEngagementRollup).where(LearnerEngagementRollup.user_id == user_id)
        ).scalar_one_or_none()

        if existing:
            existing.completion_rate = completion_rate
            existing.skip_rate = skip_rate
            existing.avg_session_time = avg_session
            existing.total_events = total_events
            existing.updated_at = datetime.now(timezone.utc)
            rollup = existing
        else:
            rollup = LearnerEngagementRollup(
                user_id=user_id,
                completion_rate=completion_rate,
                skip_rate=skip_rate,
                avg_session_time=avg_session,
                total_events=total_events,
                updated_at=datetime.now(timezone.utc)
            )
            self.db.add(rollup)

        return rollup

    def get_completed_content_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        """FR-502: Fetch set of content_ids completed by learner."""
        stmt = (
            select(InteractionEvent.content_id)
            .where(
                InteractionEvent.user_id == user_id,
                InteractionEvent.event_type == "completed"
            )
        )
        results = self.db.execute(stmt).scalars().all()
        return set(results)

    def get_successful_completions(self, min_mastery: float) -> dict:
        """
        FR-508: {user_id: {content_id}} for completions that count as successful, meaning the learner's
        current mastery of the item's topic is at least min_mastery. Anonymised rows are excluded.
        """
        stmt = (
            select(InteractionEvent.user_id, InteractionEvent.content_id)
            .join(ContentItem, ContentItem.content_id == InteractionEvent.content_id)
            .join(
                MasteryScore,
                (MasteryScore.user_id == InteractionEvent.user_id)
                & (MasteryScore.topic_id == ContentItem.topic_id),
            )
            .where(
                InteractionEvent.event_type == "completed",
                InteractionEvent.user_id.is_not(None),
                MasteryScore.score >= min_mastery,
            )
            .distinct()
        )
        completions: dict = {}
        for user_id, content_id in self.db.execute(stmt).all():
            completions.setdefault(user_id, set()).add(content_id)
        return completions

    def get_engagement_rollup(self, user_id: uuid.UUID) -> Optional[LearnerEngagementRollup]:
        """FR-307: Fetch learner engagement rollup."""
        stmt = select(LearnerEngagementRollup).where(LearnerEngagementRollup.user_id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_learner_engagement(self, user_id: uuid.UUID) -> Optional[LearnerEngagementRollup]:
        stmt = select(LearnerEngagementRollup).where(LearnerEngagementRollup.user_id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_attempts_for_user(
        self,
        user_id: uuid.UUID,
        question_ids: Optional[List[uuid.UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Attempt]:
        """FR-703, FR-704: List learner attempts with optional question and date range filtering."""
        if question_ids is not None and len(question_ids) == 0:
            return []
        stmt = select(Attempt).where(Attempt.user_id == user_id)
        if question_ids is not None:
            stmt = stmt.where(Attempt.question_id.in_(question_ids))
        if start_date:
            stmt = stmt.where(Attempt.answered_at >= start_date)
        if end_date:
            stmt = stmt.where(Attempt.answered_at <= end_date)
        stmt = stmt.order_by(Attempt.answered_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def list_events_for_user(
        self,
        user_id: uuid.UUID,
        content_ids: Optional[List[uuid.UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[InteractionEvent]:
        """FR-703, FR-704: List learner interaction events with optional content and date range filtering."""
        if content_ids is not None and len(content_ids) == 0:
            return []
        stmt = select(InteractionEvent).where(InteractionEvent.user_id == user_id)
        if content_ids is not None:
            stmt = stmt.where(InteractionEvent.content_id.in_(content_ids))
        if start_date:
            stmt = stmt.where(InteractionEvent.timestamp >= start_date)
        if end_date:
            stmt = stmt.where(InteractionEvent.timestamp <= end_date)
        stmt = stmt.order_by(InteractionEvent.timestamp.desc())
        return list(self.db.execute(stmt).scalars().all())

    def get_user_activity_dates(self, user_id: uuid.UUID) -> List[datetime]:
        """FR-701: Fetch timestamps of user activity for calculating streaks."""
        stmt1 = select(Attempt.answered_at).where(Attempt.user_id == user_id)
        stmt2 = select(InteractionEvent.timestamp).where(InteractionEvent.user_id == user_id)
        dates1 = self.db.execute(stmt1).scalars().all()
        dates2 = self.db.execute(stmt2).scalars().all()
        return sorted(list(dates1) + list(dates2), reverse=True)


    def anonymize_learner_data(self, user_id: uuid.UUID, anonymous_id: uuid.UUID) -> None:
        """SRS section 5.3, NFR-07: Replace learner ID with anonymous ID and delete personal mastery."""
        self.db.execute(
            update(Attempt).where(Attempt.user_id == user_id).values(user_id=anonymous_id)
        )
        self.db.execute(
            update(InteractionEvent).where(InteractionEvent.user_id == user_id).values(user_id=anonymous_id)
        )
        self.db.execute(
            delete(MasteryScore).where(MasteryScore.user_id == user_id)
        )
        self.db.execute(
            delete(LearnerEngagementRollup).where(LearnerEngagementRollup.user_id == user_id)
        )
        self.db.commit()
