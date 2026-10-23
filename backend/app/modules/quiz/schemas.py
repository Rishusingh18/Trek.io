"""
Quiz schemas (FR-601 to FR-605, NFR-08).
"""
import uuid
from typing import Optional, List
from pydantic import BaseModel
from app.modules.content.schemas import QuestionResponse


class DiagnosticStartResponse(BaseModel):
    session_id: uuid.UUID
    course_id: uuid.UUID
    total_questions: int
    first_question: Optional[QuestionResponse] = None


class QuizAnswerSubmit(BaseModel):
    attempt_id: uuid.UUID  # Client-generated attempt id for idempotency (NFR-08)
    question_id: uuid.UUID
    submitted_answer: str
    time_taken: float  # seconds


class QuizAnswerResultResponse(BaseModel):
    correct: bool
    correct_answer: str
    mastery_updated: float
    quiz_completed: bool
    next_question: Optional[QuestionResponse] = None
