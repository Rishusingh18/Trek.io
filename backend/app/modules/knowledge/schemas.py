"""
Knowledge module schemas (FR-301 to FR-307, FR-604).
"""
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class MasteryScoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    topic_id: uuid.UUID
    score: float
    confidence: float
    label: str  # "weak", "developing", "strong" (FR-306)
    updated_at: datetime


class InteractionEventCreate(BaseModel):
    content_id: Optional[uuid.UUID] = None
    event_type: str  # opened, completed, skipped, time_on_task, quiz_answered
    duration: float = 0.0


class InteractionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    timestamp: datetime
    user_id: Optional[uuid.UUID]
    content_id: Optional[uuid.UUID]
    event_type: str
    duration: float


class AttemptCreate(BaseModel):
    attempt_id: uuid.UUID
    user_id: uuid.UUID
    question_id: uuid.UUID
    correct: bool
    time_taken: float


class LearnerEngagementStatsResponse(BaseModel):
    """FR-307, FR-701: Derived per-learner completion rate, skip rate, and session time."""
    user_id: uuid.UUID
    completion_rate: float
    skip_rate: float
    avg_session_time: float
    total_events: int
    updated_at: datetime


class LearnerProgressResponse(BaseModel):
    """FR-701: Full progress dashboard containing engagement metrics, streak, and mastery scores."""
    user_id: uuid.UUID
    engagement: LearnerEngagementStatsResponse
    mastery_scores: List[MasteryScoreResponse] = []
    completion_rate: float = 0.0
    skip_rate: float = 0.0
    avg_session_time: float = 0.0
    total_events: int = 0
    streak_days: int = 0
