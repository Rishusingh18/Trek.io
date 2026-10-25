
"""
Recommender service (FR-501 to FR-510, NFR-01, NFR-08, NFR-11).
Fixed pipeline: Hard filters -> Score -> Explain.
"""
import time
import uuid
from typing import List, Optional, Dict

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.config_client import ConfigClient
from app.core.logging import logger
from app.modules.content.service import ContentService
from app.modules.content.schemas import ContentItemResponse
from app.modules.knowledge.service import KnowledgeService
from app.modules.experiments.service import ExperimentsService
from app.modules.recommender.repository import RecommenderRepository
from app.modules.recommender.strategies import STRATEGY_REGISTRY
from app.modules.recommender.strategies.base import LearnerContext, ScoredItem
from app.modules.recommender.strategies.collaborative import compute_item_similarity
from app.modules.recommender.schemas import (
    RecommendationItemResponse,
    RecommendationListResponse,
    DismissRecommendationResponse,
)

ITEM_SIMILARITY_TTL_SEC = 600
_similarity_cache: Dict[str, object] = {
    "expires": 0.0,
    "min_mastery": None,
    "value": None,
}


def clear_similarity_cache() -> None:
    """Forget the cached item-similarity table (used by tests and after bulk data changes)."""
    _similarity_cache.update(expires=0.0, min_mastery=None, value=None)


class RecommenderService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RecommenderRepository(db)
        self.content_service = ContentService(db)
        self.knowledge_service = KnowledgeService(db)
        self.experiments_service = ExperimentsService(db)
        self.config_client = ConfigClient(db)

    def _get_item_similarity(
        self, min_mastery: float
    ) -> Dict[uuid.UUID, Dict[uuid.UUID, float]]:
        """FR-508: Item similarity from successful completions, cached for a few minutes."""
        cache = _similarity_cache
        if (
            cache["value"] is not None
            and cache["min_mastery"] == min_mastery
            and time.monotonic() < cache["expires"]
        ):
            return cache["value"]

        value = compute_item_similarity(
            self.knowledge_service.get_successful_completions(min_mastery)
        )
        cache.update(
            expires=time.monotonic() + ITEM_SIMILARITY_TTL_SEC,
            min_mastery=min_mastery,
            value=value,
        )
        return value

    def _get_dynamic_weights(self) -> Dict[str, float]:
        """Read dynamic ranking weights from DB/Redis config (SRS 7.2, NFR-13)."""
        cfg = self.config_client.get(
            "ranking_weights",
            {
                "w1": settings.DEFAULT_WEIGHT_GAP,
                "w2": settings.DEFAULT_WEIGHT_FIT,
                "w3": settings.DEFAULT_WEIGHT_READY,
                "w4": settings.DEFAULT_WEIGHT_ENG,
            },
        )
        return {
            "w1": float(cfg.get("w1", 0.4)),
            "w2": float(cfg.get("w2", 0.3)),
            "w3": float(cfg.get("w3", 0.2)),
            "w4": float(cfg.get("w4", 0.1)),
        }

    def _get_thresholds(self) -> Dict[str, float]:
        """Read mastery classification thresholds (FR-306, NFR-13)."""
        cfg = self.config_client.get(
            "mastery_thresholds",
            {"weak_below": 0.40, "strong_above": 0.80},
        )
        return {
            "weak_below": float(cfg.get("weak_below", 0.40)),
            "strong_above": float(cfg.get("strong_above", 0.80)),
        }

    def _get_stretch_and_periods(self) -> Dict[str, float]:
        """Read stretch and quiet period from config."""
        mastery_cfg = self.config_client.get(
            "mastery_parameters", {"stretch": 0.10}
        )
        period_cfg = self.config_client.get(
            "quiz_and_periods", {"dismissal_quiet_period_days": 7}
        )
        return {
            "stretch": float(mastery_cfg.get("stretch", 0.10)),
            "dismissal_quiet_period_days": int(
                period_cfg.get("dismissal_quiet_period_days", 7)
            ),
        }

    def _get_reason_templates(self) -> Dict[str, str]:
        """Read admin-editable reason templates (FR-505, NFR-11)."""
        return self.config_client.get(
            "recommendation_templates",
            {
                "gap": "Strengthens a weak topic",
                "ready": "Prerequisites now met",
                "fit": "Matches your current level",
                "eng": "Format you usually complete",
            },
        )

    def get_recommendations(
        self,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        limit: int = 5,
        strategy_name: Optional[str] = None,
        arm_id: Optional[uuid.UUID] = None,
    ) -> RecommendationListResponse:
        """
        FR-501 to FR-510, NFR-01, NFR-08, NFR-11, UC-02:
        Return ordered list of top N content items with one-line reasons.
        """
        fallback_step: Optional[str] = None

        # 0. Check active experiment assignment (FR-802, FR-803)
        if arm_id is None:
            exp_info = self.experiments_service.get_learner_arm_and_strategy(user_id)
            if exp_info:
                arm_id = exp_info["arm_id"]
                if strategy_name is None:
                    strategy_name = exp_info["strategy"]

        if strategy_name is None:
            strategy_name = "rule_based"

        # 1. Load mastery vector (Redis first, fallback to DB) - NFR-01
        mastery_vector = self.knowledge_service.get_user_mastery_vector(user_id)
        mastery_map = {m.topic_id: m.score for m in mastery_vector}
        has_mastery_data = bool(mastery_vector)

        # 2. Load cached course catalog (Redis first, fallback to DB) - NFR-01
        catalog = self.content_service.get_course_catalog(course_id)
        all_candidates: List[ContentItemResponse] = []
        topic_prereqs_map: Dict[uuid.UUID, List[str]] = {}

        for topic in catalog.topics:
            topic_prereqs_map[topic.topic_id] = topic.prerequisite_topic_ids or []
            all_candidates.extend(topic.content_items)

        # Config lookups
        thresholds = self._get_thresholds()
        weak_threshold = thresholds["weak_below"]
        stretch_and_periods = self._get_stretch_and_periods()
        quiet_period_days = int(
            stretch_and_periods["dismissal_quiet_period_days"]
        )
        stretch = stretch_and_periods["stretch"]
        weights = self._get_dynamic_weights()
        templates = self._get_reason_templates()

        # 3. Hard Filters (FR-502, FR-503, FR-509)
        completed_ids = self.knowledge_service.get_completed_content_ids(user_id)
        dismissed_ids = set(
            self.repo.get_dismissed_content_ids(
                user_id, quiet_period_days=quiet_period_days
            )
        )

        filtered_candidates: List[ContentItemResponse] = []

        for item in all_candidates:
            # (a) Drop dismissed items still in quiet period (FR-509)
            if item.content_id in dismissed_ids:
                continue

            # (b) Drop completed items unless a review is due for a weak topic (FR-502)
            item_topic_mastery = mastery_map.get(item.topic_id, 0.5)
            if item.content_id in completed_ids:
                if item_topic_mastery >= weak_threshold:
                    continue

            # (c) Drop items whose prerequisite topics are still weak (FR-503)
            prereq_ids = set()

            if item.prerequisite_topic_ids:
                for pid in item.prerequisite_topic_ids:
                    try:
                        prereq_ids.add(uuid.UUID(str(pid)))
                    except (ValueError, TypeError, AttributeError):
                        pass

            if item.topic_id in topic_prereqs_map:
                for pid in topic_prereqs_map[item.topic_id]:
                    try:
                        prereq_ids.add(uuid.UUID(str(pid)))
                    except (ValueError, TypeError, AttributeError):
                        pass

            has_weak_prereq = any(
                mastery_map.get(pid, 0.5) < weak_threshold
                for pid in prereq_ids
            )

            if has_weak_prereq:
                continue

            filtered_candidates.append(item)

        # 4. Fallback chain for cold start / no mastery data (FR-510)
        scored_items: List[ScoredItem] = []

        if not has_mastery_data or not filtered_candidates:
            popular_ids = self.repo.get_popular_content_ids(limit=limit)

            if popular_ids:
                id_to_item = {item.content_id: item for item in all_candidates}
                popular_candidates = [
                    id_to_item[cid]
                    for cid in popular_ids
                    if cid in id_to_item
                ]

                if popular_candidates:
                    fallback_step = "popularity"
                    for idx, pop_item in enumerate(popular_candidates[:limit]):
                        scored_items.append(
                            ScoredItem(
                                item=pop_item,
                                score=1.0 - (idx * 0.05),
                                dominant_factor="eng",
                                reason="Popular lesson among other learners",
                            )
                        )

            if not scored_items:
                fallback_step = "entry_level"
                candidates_pool = (
                    filtered_candidates if filtered_candidates else all_candidates
                )
                entry_candidates = sorted(
                    candidates_pool,
                    key=lambda item: (item.difficulty, item.duration),
                )

                for idx, entry_item in enumerate(entry_candidates[:limit]):
                    scored_items.append(
                        ScoredItem(
                            item=entry_item,
                            score=1.0 - (idx * 0.05),
                            dominant_factor="fit",
                            reason="Entry-level concept to start your learning path",
                        )
                    )

        # 5. Normal strategy scoring with error/timeout fallback (NFR-08)
        if not scored_items:
            completion_rate = self.knowledge_service.get_learner_completion_rate(
                user_id
            )

            successful_completed_ids = set()
            item_similarity = None

            if strategy_name == "collaborative":
                successful_completions = (
                    self.knowledge_service.get_successful_completions(weak_threshold)
                )
                successful_completed_ids = successful_completions.get(
                    user_id, set()
                )
                item_similarity = self._get_item_similarity(weak_threshold)

            ctx = LearnerContext(
                user_id=user_id,
                mastery_map=mastery_map,
                completed_item_ids=completed_ids,
                dismissed_item_ids=dismissed_ids,
                successful_completed_item_ids=successful_completed_ids,
                weights=weights,
                topic_prereqs_map=topic_prereqs_map,
                overall_completion_rate=completion_rate,
                stretch=stretch,
                templates=templates,
                item_similarity=item_similarity,
            )

            strategy = STRATEGY_REGISTRY.get(
                strategy_name, STRATEGY_REGISTRY["rule_based"]
            )

            try:
                scored_items = strategy.score(ctx, filtered_candidates)
            except Exception as e:
                logger.warning(
                    f"Strategy '{strategy_name}' failed: {e}. "
                    "Retrying with rule_based fallback."
                )
                scored_items = STRATEGY_REGISTRY["rule_based"].score(
                    ctx, filtered_candidates
                )
                strategy_name = "rule_based"
                fallback_step = "rule_based"

        # Sort by score descending and take top N (FR-501)
        scored_items.sort(key=lambda scored: scored.score, reverse=True)
        top_items = scored_items[:limit]

        # 6. Log every recommendation BEFORE sending response (FR-803)
        response_items: List[RecommendationItemResponse] = []

        for rank, scored in enumerate(top_items, start=1):
            rec = self.repo.save_recommendation(
                user_id=user_id,
                content_id=scored.item.content_id,
                arm_id=arm_id,
                rank=rank,
                reason=scored.reason,
            )
            response_items.append(
                RecommendationItemResponse(
                    rec_id=rec.rec_id,
                    content_id=scored.item.content_id,
                    topic_id=scored.item.topic_id,
                    title=scored.item.title,
                    type=scored.item.type,
                    difficulty=scored.item.difficulty,
                    duration=scored.item.duration,
                    rank=rank,
                    reason=scored.reason,
                )
            )

        return RecommendationListResponse(
            items=response_items,
            strategy_used=strategy_name,
            fallback_step=fallback_step,
            arm_id=arm_id,
            total_returned=len(response_items),
        )

    def dismiss_recommendation(
        self, rec_id: uuid.UUID
    ) -> DismissRecommendationResponse:
        """FR-509: Dismiss a recommendation."""
        self.repo.dismiss_recommendation(rec_id)
        return DismissRecommendationResponse(rec_id=rec_id)

    def anonymize_learner_data(
        self, user_id: uuid.UUID, anonymous_id: uuid.UUID
    ) -> None:
        """SRS section 5.3, NFR-07: Public interface to anonymize recommendations."""
        self.repo.anonymize_learner_data(user_id, anonymous_id)
