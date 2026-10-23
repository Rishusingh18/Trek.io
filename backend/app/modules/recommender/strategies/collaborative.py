"""
Collaborative filtering recommendation strategy stub (FR-506, FR-508).
Uses paths that similar learners completed successfully.
"""
from typing import List
from app.modules.content.schemas import ContentItemResponse
from app.modules.recommender.strategies.base import RecommendationStrategy, LearnerContext, ScoredItem


class CollaborativeStrategy(RecommendationStrategy):
    name: str = "collaborative"

    def score(self, ctx: LearnerContext, candidates: List[ContentItemResponse]) -> List[ScoredItem]:
        """FR-508: Collaborative strategy stub raising NotImplementedError to exercise fallback chain."""
        raise NotImplementedError("Collaborative strategy is not yet implemented.")

