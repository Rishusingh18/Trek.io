"""
Knowledge model service (FR-301 to FR-307, FR-604, NFR-03).
Calculates mastery updates via SRS Section 7.1 formula, idle topic decay,
and caches vectors in Redis.
"""
import math
import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.redis import get_redis_client
from app.core.logging import logger
from app.core.config_client import ConfigClient
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.schemas import (
    MasteryScoreResponse,
    InteractionEventCreate,
    InteractionEventResponse,
    LearnerEngagementStatsResponse,
    LearnerProgressResponse,
)


class KnowledgeService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = KnowledgeRepository(db)
        self.config_client = ConfigClient(db)

    def _get_thresholds(self) -> Dict[str, float]:
        """Read mastery classification thresholds from dynamic config (FR-306, NFR-13)."""
        cfg = self.config_client.get("mastery_thresholds", {"weak_below": 0.40, "strong_above": 0.80})
        return {
            "weak_below": float(cfg.get("weak_below", 0.40)),
            "strong_above": float(cfg.get("strong_above", 0.80)),
        }

    def _get_algorithm_parameters(self) -> Dict[str, float]:
        """Read eta, beta, and lambda decay from dynamic config (SRS 7.1, NFR-13)."""
        cfg = self.config_client.get("mastery_parameters", {
            "learning_rate": settings.DEFAULT_ETA_LEARNING_RATE,
            "beta": settings.DEFAULT_BETA_SENSITIVITY,
            "decay_rate": settings.DEFAULT_LAMBDA_DECAY,
        })
        return {
            "eta": float(cfg.get("learning_rate", settings.DEFAULT_ETA_LEARNING_RATE)),
            "beta": float(cfg.get("beta", settings.DEFAULT_BETA_SENSITIVITY)),
            "lambda_decay": float(cfg.get("decay_rate", settings.DEFAULT_LAMBDA_DECAY)),
        }

    def get_score_label(self, score: float) -> str:
        """FR-306: Configurable labels (default: weak below 0.40, strong 0.80 or above)."""
        thresholds = self._get_thresholds()
        if score < thresholds["weak_below"]:
            return "weak"
        elif score >= thresholds["strong_above"]:
            return "strong"
        return "developing"

    def get_user_mastery_for_topic(self, user_id: uuid.UUID, topic_id: uuid.UUID) -> MasteryScoreResponse:
        """Fetch mastery score, returning default prior (0.50) if not initialized (FR-303)."""
        row = self.repo.get_mastery(user_id, topic_id)
        if not row:
            return MasteryScoreResponse(
                user_id=user_id,
                topic_id=topic_id,
                score=0.5,
                confidence=0.0,
                label=self.get_score_label(0.5),
                updated_at=datetime.now(timezone.utc)
            )
        return MasteryScoreResponse(
            user_id=row.user_id,
            topic_id=row.topic_id,
            score=row.score,
            confidence=row.confidence,
            label=self.get_score_label(row.score),
            updated_at=row.updated_at
        )

    def get_user_mastery_vector(self, user_id: uuid.UUID) -> List[MasteryScoreResponse]:
        """Fetch all mastery scores for a user, checking Redis cache first with DB fallback."""
        cache_key = f"mastery:{user_id}"
        try:
            client = get_redis_client()
            cached = client.get(cache_key)
            if cached:
                cached_data = json.loads(cached)
                return [MasteryScoreResponse(**item) for item in cached_data]
        except Exception as e:
            logger.warning(f"Failed to read mastery from Redis: {e}")

        rows = self.repo.get_all_mastery_for_user(user_id)
        results = [
            MasteryScoreResponse(
                user_id=r.user_id,
                topic_id=r.topic_id,
                score=r.score,
                confidence=r.confidence,
                label=self.get_score_label(r.score),
                updated_at=r.updated_at
            )
            for r in rows
        ]

        # Populate Redis with TTL (Redis rule: key has expiry)
        try:
            client = get_redis_client()
            client.set(cache_key, json.dumps([r.model_dump(mode="json") for r in results]), ex=3600)
        except Exception as e:
            logger.warning(f"Failed to cache mastery vector in Redis: {e}")

        return results

    def update_mastery(
        self,
        user_id: uuid.UUID,
        topic_id: uuid.UUID,
        difficulty: float,
        correct: bool,
        commit: bool = True
    ) -> MasteryScoreResponse:
        """
        SRS section 7.1 Mastery update formula:
        p_t = sigma(beta * (m_t - d))
        m_{t+1} = clip(m_t + eta * (y_t - p_t), 0, 1)
        Executed under row lock (SELECT ... FOR UPDATE) to eliminate race conditions.
        """
        params = self._get_algorithm_parameters()
        beta = params["beta"]
        eta = params["eta"]
        y_t = 1.0 if correct else 0.0

        # Row lock via SELECT ... FOR UPDATE
        current = self.repo.get_mastery(user_id, topic_id, for_update=True)
        m_t = current.score if current else 0.5
        conf = current.confidence if current else 0.0

        # Logistic prediction
        z = beta * (m_t - difficulty)
        p_t = 1.0 / (1.0 + math.exp(-max(min(z, 20.0), -20.0)))

        # Update step clipped to [0, 1]
        new_m = max(0.0, min(1.0, m_t + eta * (y_t - p_t)))
        # Increase confidence with each attempt toward 1.0
        new_conf = min(1.0, conf + 0.15)

        updated = self.repo.upsert_mastery(user_id, topic_id, new_m, new_conf)

        if commit:
            self.db.commit()
            self.db.refresh(updated)
            # Overwrite Redis cache immediately after commit so next request sees it within 1s (NFR-03)
            self.overwrite_user_mastery_cache(user_id)

        return MasteryScoreResponse(
            user_id=updated.user_id,
            topic_id=updated.topic_id,
            score=updated.score,
            confidence=updated.confidence,
            label=self.get_score_label(updated.score),
            updated_at=updated.updated_at
        )

    def apply_decay_for_idle_topics(
        self,
        user_id: uuid.UUID,
        topic_id: uuid.UUID,
        idle_days: float
    ) -> MasteryScoreResponse:
        """
        SRS section 7.1 Exponential decay for idle topics:
        m(delta_t) = m_last * exp(-lambda * delta_t)
        """
        params = self._get_algorithm_parameters()
        lambda_val = params["lambda_decay"]

        current = self.repo.get_mastery(user_id, topic_id, for_update=True)
        if not current:
            return self.get_user_mastery_for_topic(user_id, topic_id)

        decayed_score = current.score * math.exp(-lambda_val * max(0.0, idle_days))
        decayed_score = max(0.0, min(1.0, decayed_score))

        updated = self.repo.upsert_mastery(user_id, topic_id, decayed_score, current.confidence)
        self.db.commit()
        self.db.refresh(updated)
        self.overwrite_user_mastery_cache(user_id)

        return MasteryScoreResponse(
            user_id=updated.user_id,
            topic_id=updated.topic_id,
            score=updated.score,
            confidence=updated.confidence,
            label=self.get_score_label(updated.score),
            updated_at=updated.updated_at
        )

    def overwrite_user_mastery_cache(self, user_id: uuid.UUID) -> None:
        """NFR-03: Overwrite cached mastery vector in Redis with TTL."""
        cache_key = f"mastery:{user_id}"
        try:
            client = get_redis_client()
            rows = self.repo.get_all_mastery_for_user(user_id)
            data = [
                MasteryScoreResponse(
                    user_id=r.user_id,
                    topic_id=r.topic_id,
                    score=r.score,
                    confidence=r.confidence,
                    label=self.get_score_label(r.score),
                    updated_at=r.updated_at
                ).model_dump(mode="json")
                for r in rows
            ]
            client.set(cache_key, json.dumps(data), ex=3600)
        except Exception as e:
            logger.warning(f"Failed to overwrite mastery cache in Redis: {e}")

    def record_attempt(
        self,
        attempt_id: uuid.UUID,
        user_id: uuid.UUID,
        question_id: uuid.UUID,
        correct: bool,
        time_taken: float
    ):
        """FR-604, NFR-08: Idempotent attempt recording."""
        return self.repo.record_attempt(attempt_id, user_id, question_id, correct, time_taken)

    def log_interaction_event(
        self,
        user_id: Optional[uuid.UUID],
        payload: InteractionEventCreate
    ) -> InteractionEventResponse:
        """
        FR-307: Log learner engagement events and derive per-learner completion rate,
        skip rate, and average session time.
        """
        event = self.repo.log_interaction_event(
            user_id=user_id,
            content_id=payload.content_id,
            event_type=payload.event_type,
            duration=payload.duration
        )
        self.db.flush()
        if user_id:
            self.repo.derive_and_update_engagement_rollups(user_id)
        self.db.commit()
        return InteractionEventResponse.model_validate(event)

    def get_learner_progress(self, user_id: uuid.UUID) -> LearnerProgressResponse:
        """FR-701: Get learner progress with derived engagement stats and mastery vector."""
        rollup = self.repo.get_learner_engagement(user_id)
        if not rollup:
            rollup = self.repo.derive_and_update_engagement_rollups(user_id)
            self.db.commit()

        engagement_stats = LearnerEngagementStatsResponse(
            user_id=user_id,
            completion_rate=rollup.completion_rate,
            skip_rate=rollup.skip_rate,
            avg_session_time=rollup.avg_session_time,
            total_events=rollup.total_events,
            updated_at=rollup.updated_at
        )
        mastery_scores = self.get_user_mastery_vector(user_id)
        streak = self.calculate_streak_days(user_id)

        return LearnerProgressResponse(
            user_id=user_id,
            engagement=engagement_stats,
            mastery_scores=mastery_scores,
            completion_rate=rollup.completion_rate,
            skip_rate=rollup.skip_rate,
            avg_session_time=rollup.avg_session_time,
            total_events=rollup.total_events,
            streak_days=streak
        )

    def anonymize_learner_data(self, user_id: uuid.UUID, anonymous_id: uuid.UUID) -> None:
        """SRS section 5.3, NFR-07: Public interface to anonymize attempts and events."""
        self.repo.anonymize_learner_data(user_id, anonymous_id)
        try:
            client = get_redis_client()
            client.delete(f"mastery:{user_id}")
        except Exception:
            pass

    def get_completed_content_ids(self, user_id: uuid.UUID) -> set[uuid.UUID]:
        """FR-502: Return set of completed content IDs for learner."""
        return self.repo.get_completed_content_ids(user_id)

    def get_successful_completions(self, min_mastery: float) -> Dict[uuid.UUID, set]:
        """FR-508: Completions by learners whose topic mastery is at least min_mastery."""
        return self.repo.get_successful_completions(min_mastery)

    def get_learner_completion_rate(self, user_id: uuid.UUID) -> float:
        """FR-307, FR-504: Return learner's overall completion rate."""
        rollup = self.repo.get_engagement_rollup(user_id)
        if rollup and rollup.completion_rate is not None:
            return float(rollup.completion_rate)
        return 0.5

    def get_learner_engagement_rollup(self, user_id: uuid.UUID) -> Optional[LearnerEngagementRollup]:
        """FR-307, FR-701: Return engagement rollup."""
        rollup = self.repo.get_engagement_rollup(user_id)
        if not rollup:
            rollup = self.repo.derive_and_update_engagement_rollups(user_id)
            self.db.commit()
        return rollup

    def calculate_streak_days(self, user_id: uuid.UUID) -> int:
        """FR-701: Calculate consecutive active calendar days (UTC)."""
        from datetime import timedelta
        dates = self.repo.get_user_activity_dates(user_id)
        if not dates:
            return 0
        unique_days = sorted(list({d.date() for d in dates}), reverse=True)
        today = datetime.now(timezone.utc).date()

        if unique_days[0] < today - timedelta(days=1):
            return 0

        streak = 0
        current_check = unique_days[0]
        for day in unique_days:
            if day == current_check:
                streak += 1
                current_check = current_check - timedelta(days=1)
            elif day > current_check:
                continue
            else:
                break
        return streak

    def get_learner_history(
        self,
        user_id: uuid.UUID,
        question_ids: Optional[List[uuid.UUID]] = None,
        content_ids: Optional[List[uuid.UUID]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ):
        """FR-703, FR-704: Return attempts and activities for learner."""
        attempts = self.repo.list_attempts_for_user(user_id, question_ids=question_ids, start_date=start_date, end_date=end_date)
        events = self.repo.list_events_for_user(user_id, content_ids=content_ids, start_date=start_date, end_date=end_date)
        return attempts, events


