"""
Knowledge router (FR-307, FR-701, FR-104).
Thin HTTP handlers: validate input, call one service function, shape the response.
All tracking endpoints strictly require learner consent (FR-104, NFR-07).
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user, require_consent
from app.db.models.accounts import User
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.schemas import (
    InteractionEventCreate,
    InteractionEventResponse,
    MasteryScoreResponse,
    LearnerProgressResponse,
)

router = APIRouter(tags=["Knowledge & Mastery"])


@router.post("/content/{content_id}/events", response_model=InteractionEventResponse)
def log_content_event(
    content_id: uuid.UUID,
    payload: InteractionEventCreate,
    current_user: User = Depends(require_consent),  # FR-104, NFR-07: Consent gate
    db: Session = Depends(get_db)
):
    """
    FR-104, FR-307: Log learner engagement event (opened, completed, skipped, time on task)
    and update derived metrics. Requires verified consent.
    """
    payload.content_id = content_id
    service = KnowledgeService(db)
    return service.log_interaction_event(current_user.user_id, payload)


@router.get("/me/mastery", response_model=List[MasteryScoreResponse])
def get_my_mastery(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """FR-701: Get per-topic mastery scores for learner."""
    service = KnowledgeService(db)
    return service.get_user_mastery_vector(current_user.user_id)


@router.get("/me/progress", response_model=LearnerProgressResponse)
def get_my_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """FR-701: Learner progress dashboard with engagement rollups and mastery vector."""
    service = KnowledgeService(db)
    return service.get_learner_progress(current_user.user_id)
