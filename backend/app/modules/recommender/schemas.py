"""
Recommender schemas (FR-501 to FR-510).
"""
import uuid
from typing import List, Optional
from pydantic import BaseModel


class RecommendationItemResponse(BaseModel):
    rec_id: uuid.UUID
    content_id: uuid.UUID
    topic_id: uuid.UUID
    title: str
    type: str
    difficulty: int
    duration: int
    rank: int
    reason: str  # One-line explainable reason (FR-505, NFR-11)


class RecommendationListResponse(BaseModel):
    items: List[RecommendationItemResponse]
    strategy_used: str
    fallback_step: Optional[str] = None  # None, "rule_based", "diagnostic", "entry_level", "popularity" (FR-510)
    arm_id: Optional[uuid.UUID] = None
    total_returned: int


class DismissRecommendationResponse(BaseModel):
    rec_id: uuid.UUID
    status: str = "dismissed"
    message: str = "Recommendation dismissed"

