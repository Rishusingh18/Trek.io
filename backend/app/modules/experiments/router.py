"""
Experiments & Analytics router (FR-701 to FR-705, FR-801 to FR-807, NFR-02, NFR-13, UC-04).
Thin HTTP handlers: validate input, call one service function, shape the response.
"""
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import require_role, require_consent
from app.db.models.accounts import User
from app.modules.experiments.service import ExperimentsService
from app.modules.experiments.schemas import (
    ExperimentCreate,
    ExperimentResponse,
    ExperimentResultsResponse,
    ConfigUpdateRequest,
    ConfigResponse,
    StrategyToggleRequest,
    ConfigAuditResponse,
    InstructorHeatmapResponse,
    LearnerMasteryItem,
    LearnerProgressDashboardResponse,
    AtRiskReportResponse,
    LearnerHistoryResponse,
)

router = APIRouter(tags=["Experiments & Analytics"])


admin_required = Depends(require_role("administrator"))


# ---------------- Experiment Operations (FR-801, FR-804 to FR-806) ----------------
@router.post("/admin/experiments", response_model=ExperimentResponse, dependencies=[admin_required])
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db)):
    """FR-801: Admin creates an experiment."""
    return ExperimentsService(db).create_experiment(payload)


@router.get("/admin/experiments/{experiment_id}/results", response_model=ExperimentResultsResponse, dependencies=[admin_required])
def get_experiment_results(experiment_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    FR-804 to FR-806, PRD section 7:
    The admin console reads stored results only; it never runs heavy queries (NFR-02).
    """
    return ExperimentsService(db).get_experiment_results(experiment_id)


@router.post("/admin/experiments/{experiment_id}/pause", response_model=ExperimentResponse, dependencies=[admin_required])
def pause_experiment(experiment_id: uuid.UUID, db: Session = Depends(get_db)):
    """FR-806: Admin pauses experiment."""
    return ExperimentsService(db).pause_experiment(experiment_id)


# ---------------- Configuration Service (NFR-13, FR-807) ----------------
@router.put("/admin/config", response_model=ConfigResponse)
def update_config(
    payload: ConfigUpdateRequest,
    current_admin: User = Depends(require_role("administrator")),
    db: Session = Depends(get_db)
):
    """
    NFR-13: Admin updates weights, thresholds, learning rate, decay, stretch, periods.
    Records who made the change and when in the audit log.
    """
    return ExperimentsService(db).update_config(payload, changed_by=current_admin.user_id)


@router.get("/admin/config/{key}", response_model=Optional[ConfigResponse], dependencies=[admin_required])
def get_config(key: str, db: Session = Depends(get_db)):
    """NFR-13: Get config value."""
    return ExperimentsService(db).get_config(key)


@router.put("/admin/strategies/{name}", response_model=ConfigResponse)
def toggle_strategy(
    name: str,
    payload: StrategyToggleRequest,
    current_admin: User = Depends(require_role("administrator")),
    db: Session = Depends(get_db)
):
    """
    FR-807, NFR-13: Switch recommendation strategy on or off without redeploying.
    Records who made the change and when.
    """
    return ExperimentsService(db).toggle_strategy(
        strategy_name=name,
        enabled=payload.enabled,
        changed_by=current_admin.user_id
    )


@router.get("/admin/config-audits", response_model=List[ConfigAuditResponse], dependencies=[admin_required])
def list_config_audits(key: Optional[str] = None, db: Session = Depends(get_db)):
    """NFR-13: Retrieve audit log of who changed what and when."""
    return ExperimentsService(db).list_config_audits(key=key)


# ==================== Learner Dashboards (FR-701, FR-705) ====================
@router.get("/me/mastery", response_model=List[LearnerMasteryItem])
def get_learner_mastery(
    current_user: User = Depends(require_consent),
    db: Session = Depends(get_db)
):
    """FR-701: Learner views their mastery per topic."""
    return ExperimentsService(db).get_learner_mastery(current_user.user_id)


@router.get("/me/progress", response_model=LearnerProgressDashboardResponse)
def get_learner_progress(
    current_user: User = Depends(require_consent),
    db: Session = Depends(get_db)
):
    """FR-701: Learner views completion, time spent, and streaks."""
    return ExperimentsService(db).get_learner_progress(current_user.user_id)


@router.get("/me/report")
def export_learner_report(
    format: str = Query(default="csv", pattern="^(csv|pdf)$"),
    current_user: User = Depends(require_consent),
    db: Session = Depends(get_db)
):
    """FR-705: Export learner visible report as CSV or PDF."""
    content_bytes, media_type, filename = ExperimentsService(db).export_learner_report(
        user_id=current_user.user_id,
        format_type=format
    )
    return Response(
        content=content_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ==================== Instructor Dashboards (FR-702 to FR-704, UC-04, NFR-02) ====================
@router.get("/instructor/courses/{course_id}/heatmap", response_model=List[InstructorHeatmapResponse])
def get_course_heatmap(
    course_id: uuid.UUID,
    topic_id: Optional[uuid.UUID] = Query(default=None),
    current_user: User = Depends(require_role("instructor", "administrator")),
    db: Session = Depends(get_db)
):
    """
    FR-702, NFR-02, FR-704: Class mastery heatmap by topic.
    Reads precomputed rollups; enforces instructor ownership.
    """
    return ExperimentsService(db).get_instructor_heatmap(
        course_id=course_id,
        instructor=current_user,
        topic_id=topic_id
    )


@router.get("/instructor/courses/{course_id}/at-risk", response_model=AtRiskReportResponse)
def get_course_at_risk_learners(
    course_id: uuid.UUID,
    completion_rate_below: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    weak_topics_above: Optional[int] = Query(default=None, ge=0),
    current_user: User = Depends(require_role("instructor", "administrator")),
    db: Session = Depends(get_db)
):
    """
    FR-702, UC-04: Instructor at-risk learner list with configurable criteria.
    Enforces instructor ownership.
    """
    return ExperimentsService(db).get_instructor_at_risk_learners(
        course_id=course_id,
        instructor=current_user,
        completion_rate_below=completion_rate_below,
        weak_topics_above=weak_topics_above
    )


@router.get("/instructor/learners/{learner_id}/history", response_model=LearnerHistoryResponse)
def get_learner_history(
    learner_id: uuid.UUID,
    course_id: Optional[uuid.UUID] = Query(default=None),
    topic_id: Optional[uuid.UUID] = Query(default=None),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    current_user: User = Depends(require_role("instructor", "administrator")),
    db: Session = Depends(get_db)
):
    """
    FR-703, FR-704, UC-04: Instructor drills down into learner's attempts and activity history.
    Enforces instructor ownership (instructor cannot view learners outside their own courses).
    """
    return ExperimentsService(db).get_instructor_learner_history(
        learner_id=learner_id,
        instructor=current_user,
        course_id=course_id,
        topic_id=topic_id,
        start_date=start_date,
        end_date=end_date
    )

