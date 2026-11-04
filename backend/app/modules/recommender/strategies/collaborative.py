
"""
Collaborative filtering recommendation strategy (FR-506, FR-508).

Item-based: two items are similar when the same learners completed both. Similarity is the cosine of
their binary "completed by" vectors, so very popular items do not dominate:

    sim(a, b) = co(a, b) / sqrt(n(a) * n(b))

Only successful completions count (the learner's mastery of the item's topic is not weak), which keeps
the table to "paths that similar learners completed successfully" (FR-508). A candidate's raw score is
the summed similarity to the learner's successful completed items, scaled so the best candidate is 1.
It is blended into the fit(i) term of the SRS section 7.2 formula:

    fit'(i) = (1 - alpha) * fit(i) + alpha * cf(i)

With too few successful completions, or no similarity data, the rule-based scores are returned unchanged.
The similarity table is built outside the request path and passed in through LearnerContext.
"""

import math
from collections import Counter, defaultdict
from itertools import combinations
from typing import Dict, Hashable, Iterable, List

from app.modules.content.schemas import ContentItemResponse
from app.modules.recommender.strategies.base import (
    RecommendationStrategy,
    LearnerContext,
    ScoredItem,
)
from app.modules.recommender.strategies.rules import RuleBasedStrategy

MIN_COMPLETIONS = 3
DEFAULT_ALPHA = 0.5
SIMILAR_LEARNERS_REASON = "Learners like you completed this"


def compute_item_similarity(
    completions: Dict[Hashable, Iterable[Hashable]], min_support: int = 2
) -> Dict[Hashable, Dict[Hashable, float]]:
    """
    completions: {learner_id: items that learner completed successfully}.
    Returns {item: {other_item: cosine similarity}}. Pairs completed together by fewer than
    min_support learners are dropped as noise.
    """
    item_count: Counter = Counter()
    pair_count: Counter = Counter()

    for items in completions.values():
        unique = sorted(set(items), key=str)
        item_count.update(unique)
        pair_count.update(combinations(unique, 2))

    similarity: Dict[Hashable, Dict[Hashable, float]] = defaultdict(dict)

    for (a, b), co in pair_count.items():
        if co < min_support:
            continue

        score = co / math.sqrt(item_count[a] * item_count[b])
        similarity[a][b] = score
        similarity[b][a] = score

    return dict(similarity)


class CollaborativeStrategy(RecommendationStrategy):
    name: str = "collaborative"

    def __init__(self) -> None:
        self._rules = RuleBasedStrategy()

    def score(
        self,
        ctx: LearnerContext,
        candidates: List[ContentItemResponse],
    ) -> List[ScoredItem]:
        """FR-508: Blend successful-completion similarity into the rule-based fit score."""
        similarity = ctx.item_similarity or {}
        done = (
            ctx.successful_completed_item_ids
            if ctx.successful_completed_item_ids is not None
            else ctx.completed_item_ids
        )
        if len(done) < MIN_COMPLETIONS or not similarity:
            return self._rules.score(ctx, candidates)

        raw = {
            item.content_id: sum(
                similarity.get(item.content_id, {}).get(completed_id, 0.0)
                for completed_id in done
            )
            for item in candidates
        }

        top = max(raw.values(), default=0.0)

        if top <= 0.0:
            return self._rules.score(ctx, candidates)

        w1 = ctx.weights.get("w1", 0.4)
        w2 = ctx.weights.get("w2", 0.3)
        w3 = ctx.weights.get("w3", 0.2)
        w4 = ctx.weights.get("w4", 0.1)
        alpha = min(1.0, max(0.0, ctx.weights.get("alpha", DEFAULT_ALPHA)))
        templates = ctx.templates or {}

        scored: List[ScoredItem] = []

        for item in candidates:
            terms = self._rules.terms(ctx, item)
            cf = raw[item.content_id] / top

            weighted = {
                "gap": w1 * terms["gap"],
                "fit": w2 * (1 - alpha) * terms["fit"],
                "similar_learners": w2 * alpha * cf,
                "ready": w3 * terms["ready"],
                "eng": w4 * terms["eng"],
            }

            total = max(0.0, min(1.0, sum(weighted.values())))
            dominant = max(weighted, key=weighted.get)

            if dominant == "similar_learners":
                reason = templates.get(
                    "similar_learners", SIMILAR_LEARNERS_REASON
                )
            else:
                reason = templates.get(
                    dominant,
                    RuleBasedStrategy.DEFAULT_TEMPLATES.get(
                        dominant, "Recommended for you"
                    ),
                )

            scored.append(
                ScoredItem(
                    item=item,
                    score=total,
                    dominant_factor=dominant,
                    reason=reason,
                )
            )

        return scored
