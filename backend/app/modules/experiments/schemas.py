"""
Experiments, Analytics, and Config schemas (FR-702, FR-801 to FR-807, NFR-13).
"""
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class ArmCreate(BaseModel):
    name: str
    strategy: str  # rules, embeddings, collaborative
    parameters: Dict[str, Any] = {}
    allocation_share: float = 0.5


class ArmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    arm_id: uuid.UUID
    experiment_id: uuid.UUID
    name: str
    strategy: str
    parameters: dict
    allocation_share: float


class ExperimentCreate(BaseModel):
    name: str
    primary_metric: str = "post_test_gain"
    arms: List[ArmCreate]
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class ExperimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    experiment_id: uuid.UUID
    name: str
    primary_metric: str
    status: str
    arms: List[ArmResponse] = []


class ArmMetricsItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    arm_id: uuid.UUID
    arm_name: str
    strategy: str
    sample_size: int
    meets_min_sample_size: bool  # FR-805, PRD section 7: minimum of 200 learners per arm
    acceptance_rate: float
    acceptance_rate_ci: Dict[str, float]  # 95% confidence interval {"lower": ..., "upper": ...}
    completion_rate_8w: float
    completion_rate_8w_ci: Dict[str, float]
    post_test_gain: float
    post_test_gain_ci: Dict[str, float]
    p_value: Optional[float] = None
    is_significant: bool = False
    guardrail_dropout_rate: float = 0.0
    guardrail_abandonment_rate: float = 0.0
    guardrail_breached: bool = False


class ExperimentResultsResponse(BaseModel):
    """FR-804, FR-805, FR-806: Per-arm results with significance, CI, and guardrails."""
    experiment_id: uuid.UUID
    name: str
    status: str
    is_paused: bool
    primary_metric: str
    arms_metrics: List[ArmMetricsItem]
    total_learners: int
    meets_minimum_sample_size_all_arms: bool
    guardrail_breach_detected: bool


# ---------------- Config Service Schemas (NFR-13, FR-807) ----------------
class ConfigUpdateRequest(BaseModel):
    """NFR-13: Change weights, thresholds, learning rates, periods, or flags."""
    key: str
    value: Dict[str, Any]
    description: Optional[str] = None


class StrategyToggleRequest(BaseModel):
    """FR-807: Switch strategy on or off without redeploying."""
    enabled: bool


class ConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Dict[str, Any]
    description: Optional[str] = None
    updated_at: datetime


class ConfigAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Dict[str, Any]
    changed_by_user_id: Optional[uuid.UUID] = None
    changed_at: datetime


class InstructorHeatmapResponse(BaseModel):
    """FR-702, NFR-02: Instructor class topic mastery and at-risk metrics."""
    model_config = ConfigDict(from_attributes=True)

    course_id: uuid.UUID
    topic_id: uuid.UUID
    average_mastery: float
    learner_count: int
    weak_count: int


# ---------------- Learner Dashboard Schemas (FR-701, FR-705) ----------------
class LearnerMasteryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    topic_id: uuid.UUID
    score: float
    confidence: float
    label: str
    updated_at: datetime


class LearnerProgressDashboardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    completion_rate: float
    skip_rate: float
    avg_session_time: float
    total_events: int
    streak_days: int


# ---------------- Instructor Dashboard Schemas (FR-702 to FR-704, UC-04) ----------------
class AtRiskLearnerItem(BaseModel):
    user_id: uuid.UUID
    email: str
    completion_rate: float
    weak_topics_count: int
    risk_reasons: List[str]


class AtRiskReportResponse(BaseModel):
    course_id: uuid.UUID
    criteria: Dict[str, Any]
    total_learners_at_risk: int
    at_risk_learners: List[AtRiskLearnerItem]


class LearnerAttemptHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attempt_id: uuid.UUID
    question_id: uuid.UUID
    correct: bool
    time_taken: float
    answered_at: datetime


class LearnerActivityHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    content_id: Optional[uuid.UUID] = None
    event_type: str
    duration: int
    created_at: datetime


class LearnerHistoryResponse(BaseModel):
    user_id: uuid.UUID
    course_id: Optional[uuid.UUID] = None
    attempts: List[LearnerAttemptHistoryItem]
    activities: List[LearnerActivityHistoryItem]

