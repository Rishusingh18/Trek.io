"""
Integration test for immediate mastery visibility adhering to NFR-03.
Requirement NFR-03:
"When a learner submits a quiz answer, the mastery update must be visible
on the very next request, within 1 second."
"""
import uuid
import time
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import create_access_token, get_password_hash
from app.modules.accounts.repository import AccountsRepository
from app.modules.content.service import ContentService
from app.modules.content.schemas import CourseCreate, TopicCreate, QuestionCreate


def test_nfr03_quiz_answer_mastery_visible_next_request(client: TestClient, db_session: Session):
    """
    NFR-03: Submitting a quiz answer updates the database and cache such that
    the very next request retrieves the updated mastery score within 1 second.
    """
    accounts_repo = AccountsRepository(db_session)
    content_svc = ContentService(db_session)

    suffix = uuid.uuid4().hex[:6]

    # Create learner with consent
    learner = accounts_repo.create_user(f"nfr03_learner_{suffix}@test.com", get_password_hash("pass123"), "learner")
    accounts_repo.record_consent(learner.user_id)
    learner_auth = {"Authorization": f"Bearer {create_access_token(learner.user_id, role='learner')}"}

    # Create course, topic, question
    course = content_svc.create_course(CourseCreate(
        title=f"Fast Mastery Course {suffix}",
        description="Testing NFR-03 latency and immediate visibility"
    ))
    topic = content_svc.create_topic(TopicCreate(
        course_id=course.course_id,
        name=f"Fast Topic {suffix}"
    ))
    question = content_svc.create_question(QuestionCreate(
        topic_id=topic.topic_id,
        prompt="What is 2 + 2 in Python?",
        difficulty=0.4,
        correct_answer="4",
        options=["3", "4", "5", "6"]
    ))

    # 1. Start Diagnostic Quiz Session
    diag_res = client.post(f"/v1/courses/{course.course_id}/diagnostic", headers=learner_auth)
    assert diag_res.status_code == 200
    diag_body = diag_res.json()
    session_id = diag_body["session_id"]
    first_question = diag_body["first_question"]
    assert first_question is not None

    # 2. Benchmark time from submission to reading the very next request
    t_start = time.perf_counter()

    attempt_id = str(uuid.uuid4())
    ans_res = client.post(
        f"/v1/quiz-sessions/{session_id}/answers",
        json={
            "attempt_id": attempt_id,
            "question_id": first_question["question_id"],
            "submitted_answer": "4",  # correct answer
            "time_taken": 18.5
        },
        headers=learner_auth
    )
    assert ans_res.status_code == 200
    ans_body = ans_res.json()
    assert ans_body["correct"] is True
    graded_score = ans_body["mastery_updated"]

    # 3. Very next request: GET /v1/me/mastery
    next_req_res = client.get("/v1/me/mastery", headers=learner_auth)
    t_end = time.perf_counter()

    elapsed = t_end - t_start

    assert next_req_res.status_code == 200
    masteries = next_req_res.json()
    assert len(masteries) >= 1

    topic_mastery = next((m for m in masteries if m["topic_id"] == str(topic.topic_id)), None)
    assert topic_mastery is not None

    # Assert immediate consistency: mastery visible on very next request matches graded score
    assert topic_mastery["score"] == graded_score
    assert topic_mastery["score"] > 0.50  # Initial default prior was 0.50, correct answer increased it

    # Assert NFR-03 timing constraint: visible within 1 second
    assert elapsed < 1.0, f"NFR-03 breach: End-to-end latency {elapsed:.3f}s exceeds 1.0s limit"
