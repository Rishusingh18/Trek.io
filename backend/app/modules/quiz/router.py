"""
Adaptive Quiz router (FR-601 to FR-605, UC-01, UC-03).
Thin HTTP handlers: validate input, call one service function, shape the response.
"""
import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.db.models.accounts import User
from app.modules.quiz.service import QuizService
from app.modules.quiz.schemas import (
    DiagnosticStartResponse,
    QuizAnswerSubmit,
    QuizAnswerResultResponse,
)

router = APIRouter(tags=["Quiz"])


@router.post("/courses/{course_id}/diagnostic", response_model=DiagnosticStartResponse)
def start_diagnostic_quiz(
    course_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """FR-601, UC-01: Start diagnostic quiz across all topics for the given course."""
    service = QuizService(db)
    return service.start_diagnostic(user_id=current_user.user_id, course_id=course_id)


@router.post("/quiz-sessions/{session_id}/answers", response_model=QuizAnswerResultResponse)
def submit_quiz_answer(
    session_id: uuid.UUID,
    payload: QuizAnswerSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    FR-602, FR-604, UC-03, NFR-08:
    Submit answer, insert attempt, update mastery, and fetch adaptive next question
    in one atomic transaction.
    """
    service = QuizService(db)
    return service.submit_answer(
        session_id=session_id,
        user_id=current_user.user_id,
        payload=payload
    )
