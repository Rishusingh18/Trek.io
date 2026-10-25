"""
Recommendation strategy interface (FR-506, NFR-12).
All recommendation algorithms implement this single common interface.
"""
from typing import Protocol, List, Dict
import uuid
from dataclasses import dataclass
from app.modules.content.schemas import ContentItemResponse


@dataclass
class LearnerContext:
    user_id: uuid.UUID
    mastery_map: Dict[uuid.UUID, float]  # topic_id -> mastery score in [0, 1]
    completed_item_ids: set[uuid.UUID]
    dismissed_item_ids: set[uuid.UUID]
    weights: Dict[str, float]  # w1, w2, w3, w4
    topic_prereqs_map: Dict[uuid.UUID, List[str]] = None
    completion_rates_by_type: Dict[str, float] = None
    overall_completion_rate: float = 0.5
    stretch: float = 0.10
    templates: Dict[str, str] = None
    item_similarity: Dict[uuid.UUID, Dict[uuid.UUID, float]] = None  # content_id -> {content_id: similarity}
    successful_completed_item_ids: set[uuid.UUID] = None
    catalog: List[ContentItemResponse] = None  # all course items; lets a strategy look up completed items


@dataclass
class ScoredItem:
    item: ContentItemResponse
    score: float
    dominant_factor: str  # "gap", "fit", "ready", "eng"
    reason: str



class RecommendationStrategy(Protocol):
    name: str

    def score(self, ctx: LearnerContext, candidates: List[ContentItemResponse]) -> List[ScoredItem]:
        """Return a score in [0, 1] and the dominant factor / reason for each candidate."""
        ...
