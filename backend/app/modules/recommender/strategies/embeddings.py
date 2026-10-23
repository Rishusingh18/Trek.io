"""
Embeddings-based recommendation strategy stub (FR-506, FR-507).
Computes content similarity from title, description and tags.
"""
from typing import List
from app.modules.content.schemas import ContentItemResponse
from app.modules.recommender.strategies.base import RecommendationStrategy, LearnerContext, ScoredItem


class EmbeddingsStrategy(RecommendationStrategy):
    name: str = "embeddings"

    def score(self, ctx: LearnerContext, candidates: List[ContentItemResponse]) -> List[ScoredItem]:
        """FR-507: Embeddings strategy stub raising NotImplementedError to exercise fallback chain."""
        raise NotImplementedError("Embeddings strategy is not yet implemented.")

