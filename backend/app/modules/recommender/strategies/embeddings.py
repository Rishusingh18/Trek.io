
"""Embeddings-based recommendation strategy (FR-506, FR-507)."""
from functools import lru_cache
from typing import List

from sentence_transformers import SentenceTransformer

from app.modules.content.schemas import ContentItemResponse
from app.modules.recommender.strategies.base import (
    RecommendationStrategy,
    LearnerContext,
    ScoredItem,
)
from app.modules.recommender.strategies.rules import RuleBasedStrategy


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
SEMANTIC_WEIGHT = 0.65
RULE_WEIGHT = 0.35


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    """Load the downloaded model once, using local files only."""
    return SentenceTransformer(
        MODEL_NAME,
        model_kwargs={"local_files_only": True},
        tokenizer_kwargs={"local_files_only": True},
    )


class EmbeddingsStrategy(RecommendationStrategy):
    name: str = "embeddings"

    @staticmethod
    def _text(item: ContentItemResponse) -> str:
        description = getattr(item, "description", None) or ""
        tags = getattr(item, "tags", None) or []

        return (
            f"Title: {item.title}. "
            f"Description: {description}. "
            f"Tags: {', '.join(tags)}. "
            f"Content type: {item.type}. "
            f"Difficulty level: {item.difficulty} out of 5."
        )

    def score(
        self,
        ctx: LearnerContext,
        candidates: List[ContentItemResponse],
    ) -> List[ScoredItem]:
        if not candidates:
            return []

        rule_scores = RuleBasedStrategy().score(ctx, candidates)
        completed_items = ctx.completed_items or []

        # Without history, retain the established rule-based ranking.
        if not completed_items:
            return rule_scores

        model = _load_model()
        texts = [
            self._text(item)
            for item in completed_items + candidates
        ]
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )

        history_count = len(completed_items)
        history_embeddings = embeddings[:history_count]
        candidate_embeddings = embeddings[history_count:]

        scored = []
        for index, item in enumerate(candidates):
            # Normalized embeddings make the dot product cosine similarity.
            similarities = candidate_embeddings[index] @ history_embeddings.T
            max_similarity = float(similarities.max())

            # Map cosine similarity from [-1, 1] into [0, 1].
            semantic_score = max(0.0, min(1.0, (max_similarity + 1.0) / 2.0))
            rule_score = rule_scores[index]

            combined_score = (
                SEMANTIC_WEIGHT * semantic_score
                + RULE_WEIGHT * rule_score.score
            )

            if semantic_score >= rule_score.score:
                dominant_factor = "fit"
                reason = "Similar to content you've completed"
            else:
                dominant_factor = rule_score.dominant_factor
                reason = rule_score.reason

            scored.append(
                ScoredItem(
                    item=item,
                    score=max(0.0, min(1.0, float(combined_score))),
                    dominant_factor=dominant_factor,
                    reason=reason,
                )
            )

        return scored
