"""
Adaptive quiz service (FR-601 to FR-605, UC-01, UC-03, NFR-03, NFR-08).
Coordinates between ContentService and KnowledgeService.
Executes answer grading, attempt logging, mastery update, and event logging in ONE atomic database transaction.
"""
import uuid
import json
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.redis import get_redis_client
from app.core.logging import logger
from app.core.config_client import ConfigClient
from app.modules.content.service import ContentService
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.schemas import InteractionEventCreate
from app.modules.quiz.schemas import (
    DiagnosticStartResponse,
    QuizAnswerSubmit,
    QuizAnswerResultResponse,
)
from app.modules.content.schemas import QuestionResponse

# In-memory session store fallback if Redis is unavailable
_memory_sessions: Dict[str, Dict[str, Any]] = {}


class QuizService:
    def __init__(self, db: Session):
        self.db = db
        self.content_service = ContentService(db)
        self.knowledge_service = KnowledgeService(db)
        self.config_client = ConfigClient(db)

    def _get_session_state(self, session_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        key = f"quiz_session:{session_id}"
        try:
            client = get_redis_client()
            cached = client.get(key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        return _memory_sessions.get(str(session_id))

    def _save_session_state(self, session_id: uuid.UUID, state: Dict[str, Any]) -> None:
        key = f"quiz_session:{session_id}"
        _memory_sessions[str(session_id)] = state
        try:
            client = get_redis_client()
            client.set(key, json.dumps(state), ex=7200)  # 2 hours expiry
        except Exception as e:
            logger.warning(f"Failed to cache quiz session state: {e}")

    def start_diagnostic(self, user_id: uuid.UUID, course_id: uuid.UUID) -> DiagnosticStartResponse:
        """
        FR-601, UC-01: Start diagnostic quiz covering every topic in the course.
        """
        topics = self.content_service.get_topics_for_course(course_id)
        session_id = uuid.uuid4()

        diagnostic_questions: List[QuestionResponse] = []
        for topic in topics:
            questions = self.content_service.get_questions_for_topic(topic.topic_id)
            if questions:
                # Pick entry-level question for topic diagnostic
                questions.sort(key=lambda q: q.difficulty)
                diagnostic_questions.append(questions[0])

        first_q = diagnostic_questions[0] if diagnostic_questions else None

        state = {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "course_id": str(course_id),
            "is_diagnostic": True,
            "diagnostic_question_ids": [str(q.question_id) for q in diagnostic_questions],
            "answered_question_ids": [],
            "consecutive_correct": 0,
            "consecutive_incorrect": 0,
            "difficulty_step_offset": 0.0,
            "question_count": 0,
        }
        self._save_session_state(session_id, state)

        return DiagnosticStartResponse(
            session_id=session_id,
            course_id=course_id,
            total_questions=len(diagnostic_questions),
            first_question=first_q
        )

    def submit_answer(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        payload: QuizAnswerSubmit
    ) -> QuizAnswerResultResponse:
        """
        FR-602, FR-604, NFR-03, NFR-08, UC-03:
        In ONE database transaction:
        1. Grade the answer
        2. Insert the attempt (with client-generated attempt_id for idempotency)
        3. Call knowledge.service to update mastery under row lock
        4. Append answer event to interaction_events
        5. Commit transaction and overwrite Redis cache
        """
        # NFR-08: Check idempotency via attempt_id
        existing_attempt = self.knowledge_service.repo.get_attempt(payload.attempt_id)
        question = self.content_service.get_question(payload.question_id)
        is_correct = (question.correct_answer.strip().lower() == payload.submitted_answer.strip().lower())

        if existing_attempt:
            # Retried request: return existing state without duplicate mutation
            mastery = self.knowledge_service.get_user_mastery_for_topic(user_id, question.topic_id)
            return QuizAnswerResultResponse(
                correct=existing_attempt.correct,
                correct_answer=question.correct_answer,
                mastery_updated=mastery.score,
                quiz_completed=mastery.confidence >= 0.85,
                next_question=None
            )

        # Execute in ONE atomic database transaction
        try:
            # 1. Insert attempt
            self.knowledge_service.repo.record_attempt(
                attempt_id=payload.attempt_id,
                user_id=user_id,
                question_id=payload.question_id,
                correct=is_correct,
                time_taken=payload.time_taken
            )

            # 2. Update mastery under row lock (commit=False to keep atomic)
            updated_mastery = self.knowledge_service.update_mastery(
                user_id=user_id,
                topic_id=question.topic_id,
                difficulty=question.difficulty,
                correct=is_correct,
                commit=False
            )

            # 3. Append answer event to event log
            self.knowledge_service.repo.log_interaction_event(
                user_id=user_id,
                content_id=None,
                event_type="quiz_answered",
                duration=payload.time_taken
            )

            # 4. Commit atomic transaction
            self.db.commit()

            # 5. Overwrite Redis mastery vector immediately after commit (NFR-03)
            self.knowledge_service.overwrite_user_mastery_cache(user_id)

        except Exception as e:
            self.db.rollback()
            raise e

        # Update Session Adaptive Stepping State (SRS section 7.3, UC-03)
        session_state = self._get_session_state(session_id) or {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "course_id": None,
            "answered_question_ids": [],
            "consecutive_correct": 0,
            "consecutive_incorrect": 0,
            "difficulty_step_offset": 0.0,
            "question_count": 0,
        }

        answered_ids = set(session_state.get("answered_question_ids", []))
        answered_ids.add(str(payload.question_id))
        session_state["answered_question_ids"] = list(answered_ids)
        session_state["question_count"] = session_state.get("question_count", 0) + 1

        consec_correct = session_state.get("consecutive_correct", 0)
        consec_incorrect = session_state.get("consecutive_incorrect", 0)
        step_offset = session_state.get("difficulty_step_offset", 0.0)

        if is_correct:
            consec_correct += 1
            consec_incorrect = 0
            # UC-03: Step up one level after 3 correct in a row
            if consec_correct >= 3:
                step_offset = min(0.40, step_offset + 0.15)
                consec_correct = 0  # reset streak on step
        else:
            consec_incorrect += 1
            consec_correct = 0
            # UC-03: Step down one level after 2 incorrect in a row
            if consec_incorrect >= 2:
                step_offset = max(-0.40, step_offset - 0.15)
                consec_incorrect = 0  # reset streak on step

        session_state["consecutive_correct"] = consec_correct
        session_state["consecutive_incorrect"] = consec_incorrect
        session_state["difficulty_step_offset"] = step_offset

        # Check stop rule (FR-605): confidence passes threshold (>= 0.85) or max length (10)
        quiz_completed = (
            updated_mastery.confidence >= 0.85 or
            session_state["question_count"] >= 10
        )

        next_q: Optional[QuestionResponse] = None
        if not quiz_completed:
            candidates = self.content_service.get_questions_for_topic(question.topic_id)
            # FR-603: Never repeat a question in a session
            eligible = [q for q in candidates if str(q.question_id) not in answered_ids]

            if eligible:
                # Target difficulty = clip(mastery + stretch, 0, 1) + step_offset (SRS 7.3)
                base_target = min(1.0, max(0.0, updated_mastery.score + settings.DEFAULT_STRETCH))
                target_diff = min(1.0, max(0.0, base_target + step_offset))
                eligible.sort(key=lambda q: abs(q.difficulty - target_diff))
                next_q = eligible[0]
            else:
                quiz_completed = True

        self._save_session_state(session_id, session_state)

        return QuizAnswerResultResponse(
            correct=is_correct,
            correct_answer=question.correct_answer,
            mastery_updated=updated_mastery.score,
            quiz_completed=quiz_completed,
            next_question=next_q
        )
