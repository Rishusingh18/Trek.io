"""
Rule-based recommendation strategy (SRS section 7.2, FR-504, FR-505, FR-506).
Calculates: S(i) = w1*gap(i) + w2*fit(i) + w3*ready(i) + w4*eng(i).
"""
import uuid
from typing import List, Dict
from app.modules.content.schemas import ContentItemResponse
from app.modules.recommender.strategies.base import RecommendationStrategy, LearnerContext, ScoredItem


class RuleBasedStrategy(RecommendationStrategy):
    name: str = "rule_based"

    DEFAULT_TEMPLATES: Dict[str, str] = {
        "gap": "Strengthens a weak topic",
        "ready": "Prerequisites now met",
        "fit": "Matches your current level",
        "eng": "Format you usually complete",
    }

    def score(self, ctx: LearnerContext, candidates: List[ContentItemResponse]) -> List[ScoredItem]:
        """
        SRS section 7.2 recommendation ranking formula:
        S(i) = w1*gap(i) + w2*fit(i) + w3*ready(i) + w4*eng(i)
        """
        w1 = ctx.weights.get("w1", 0.4)
        w2 = ctx.weights.get("w2", 0.3)
        w3 = ctx.weights.get("w3", 0.2)
        w4 = ctx.weights.get("w4", 0.1)
        stretch = getattr(ctx, "stretch", 0.10)
        templates = ctx.templates or self.DEFAULT_TEMPLATES

        scored: List[ScoredItem] = []
        for item in candidates:
            # 1. gap(i): 1 minus mastery of the item's topic (0 to 1, bigger for weaker topics)
            topic_mastery = ctx.mastery_map.get(item.topic_id, 0.5)
            gap = max(0.0, min(1.0, 1.0 - topic_mastery))

            # 2. fit(i): closeness of item difficulty to mastery plus stretch
            # difficulty scaled to [0, 1] from [1, 5]
            item_diff_norm = max(0.0, min(1.0, (item.difficulty - 1.0) / 4.0)) if item.difficulty > 1 else 0.0
            target_diff = max(0.0, min(1.0, topic_mastery + stretch))
            fit = max(0.0, min(1.0, 1.0 - abs(item_diff_norm - target_diff)))

            # 3. ready(i): lowest mastery among prerequisite topics
            prereq_ids = set()
            if item.prerequisite_topic_ids:
                for pid in item.prerequisite_topic_ids:
                    try:
                        prereq_ids.add(uuid.UUID(str(pid)))
                    except Exception:
                        pass
            if ctx.topic_prereqs_map and item.topic_id in ctx.topic_prereqs_map:
                for pid in ctx.topic_prereqs_map[item.topic_id]:
                    try:
                        prereq_ids.add(uuid.UUID(str(pid)))
                    except Exception:
                        pass

            if prereq_ids:
                prereq_masteries = [ctx.mastery_map.get(pid, 0.5) for pid in prereq_ids]
                ready = min(prereq_masteries)
            else:
                ready = 1.0

            # 4. eng(i): learner's historical completion rate for this content type
            eng = 0.5
            if ctx.completion_rates_by_type and item.type in ctx.completion_rates_by_type:
                eng = ctx.completion_rates_by_type[item.type]
            elif hasattr(ctx, "overall_completion_rate") and ctx.overall_completion_rate is not None:
                eng = ctx.overall_completion_rate

            # Weighted components
            weighted_terms = {
                "gap": w1 * gap,
                "fit": w2 * fit,
                "ready": w3 * ready,
                "eng": w4 * eng,
            }
            total_score = sum(weighted_terms.values())
            # Clamp to [0, 1]
            total_score = max(0.0, min(1.0, total_score))

            # Identify dominant factor
            dominant_factor = max(weighted_terms, key=weighted_terms.get)
            reason = templates.get(dominant_factor, self.DEFAULT_TEMPLATES.get(dominant_factor, "Recommended for you"))

            scored.append(
                ScoredItem(
                    item=item,
                    score=total_score,
                    dominant_factor=dominant_factor,
                    reason=reason
                )
            )

        return scored

