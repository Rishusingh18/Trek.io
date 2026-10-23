"""
Recommender router (FR-501, FR-505, FR-509, FR-104).
Thin HTTP handlers: validate input, call one service function, shape the response.
"""
import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import require_consent
from app.db.models.accounts import User
from app.modules.recommender.service import RecommenderService
from app.modules.recommender.schemas import (
    RecommendationListResponse,
    DismissRecommendationResponse,
)

router = APIRouter(tags=["Recommender"])


@router.get("/courses/{course_id}/recommendations", response_model=RecommendationListResponse)
def get_recommendations(
    course_id: uuid.UUID,
    limit: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(require_consent),
    db: Session = Depends(get_db)
):
    """FR-501, FR-505, UC-02, FR-104: Get personalized learning path recommendations with explainable reasons."""
    service = RecommenderService(db)
    return service.get_recommendations(
        user_id=current_user.user_id,
        course_id=course_id,
        limit=limit
    )


@router.post("/recommendations/{rec_id}/dismiss", response_model=DismissRecommendationResponse)
def dismiss_recommendation(
    rec_id: uuid.UUID,
    current_user: User = Depends(require_consent),
    db: Session = Depends(get_db)
):
    """FR-509, FR-104: Learner dismisses recommendation."""
    service = RecommenderService(db)
    return service.dismiss_recommendation(rec_id)

