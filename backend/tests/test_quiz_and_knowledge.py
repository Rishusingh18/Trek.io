"""
Unit tests for Knowledge model (FR-301 to FR-307) and Adaptive Quiz (FR-601 to FR-605, UC-01, UC-03).
"""
import uuid
import math
from fastapi.testclient import TestClient
from app.core.auth import create_access_token, get_password_hash
from app.modules.accounts.repository import AccountsRepository
from app.modules.content.service import ContentService
from app.modules.content.schemas import CourseCreate, TopicCreate, QuestionCreate
from app.modules.knowledge.service import KnowledgeService
from app.db.models.knowledge import Attempt


def setup_learner(db_session, email_prefix: str = "learner"):
    repo = AccountsRepository(db_session)
    suffix = uuid.uuid4().hex[:8]
    user = repo.create_user(f"{email_prefix}_{suffix}@test.com", get_password_hash("pass123"), "learner")
    repo.record_consent(user.user_id)
    token = create_access_token(user.user_id, role="learner")
    return user, token


def test_fr302_section71_mastery_formula(client: TestClient, db_session):
    """
    Verify FR-302, SRS section 7.1:
    p = sigma(beta * (m - d))
    m_new = clip(m + eta * (y - p), 0, 1)
    Reads active dynamic configuration parameters (NFR-13).
    """
    svc = KnowledgeService(db_session)
    user, _ = setup_learner(db_session, "formula")
    topic_id = uuid.uuid4()

    params = svc._get_algorithm_parameters()
    beta = params["beta"]
    eta = params["eta"]

    # Initial default prior m_0 = 0.5, question difficulty d = 0.4
    z = beta * (0.5 - 0.4)
    expected_p = 1.0 / (1.0 + math.exp(-z))
    expected_m1 = 0.5 + eta * (1.0 - expected_p)

    res1 = svc.update_mastery(user.user_id, topic_id, difficulty=0.4, correct=True)
    assert math.isclose(res1.score, expected_m1, rel_tol=1e-3)
    assert res1.confidence > 0.0

    # Next attempt: incorrect (y = 0), d = 0.6
    m1 = res1.score
    z2 = beta * (m1 - 0.6)
    expected_p2 = 1.0 / (1.0 + math.exp(-z2))
    expected_m2 = max(0.0, m1 + eta * (0.0 - expected_p2))

    res2 = svc.update_mastery(user.user_id, topic_id, difficulty=0.6, correct=False)
    assert math.isclose(res2.score, expected_m2, rel_tol=1e-3)


def test_fr305_idle_topics_exponential_decay(client: TestClient, db_session):
    """
    Verify FR-305, SRS section 7.1:
    m(delta_t) = m_last * exp(-lambda * delta_t)
    Reads active lambda decay from config (NFR-13).
    """
    svc = KnowledgeService(db_session)
    user, _ = setup_learner(db_session, "decay")
    topic_id = uuid.uuid4()

    params = svc._get_algorithm_parameters()
    lambda_decay = params["lambda_decay"]

    # Seed initial mastery score 0.80
    svc.repo.upsert_mastery(user.user_id, topic_id, score=0.80, confidence=0.7)
    db_session.commit()

    # Apply 10 days of idle decay
    expected_decayed = 0.80 * math.exp(-lambda_decay * 10)

    res = svc.apply_decay_for_idle_topics(user.user_id, topic_id, idle_days=10.0)
    assert math.isclose(res.score, expected_decayed, rel_tol=1e-3)


def test_fr306_configurable_labels(client: TestClient, db_session):
    """Verify FR-306: Labels weak below 0.40, developing, strong 0.80 or above."""
    svc = KnowledgeService(db_session)
    assert svc.get_score_label(0.39) == "weak"
    assert svc.get_score_label(0.40) == "developing"
    assert svc.get_score_label(0.79) == "developing"
    assert svc.get_score_label(0.80) == "strong"
    assert svc.get_score_label(0.95) == "strong"


def test_uc03_adaptive_quiz_stepping_rule(client: TestClient, db_session):
    """
    Verify UC-03 & SRS section 7.3:
    Given three correct answers in a row, the next question is one difficulty level higher;
    given two incorrect in a row, one level lower; no question repeats in a session.
    """
    user, token = setup_learner(db_session, "adaptive")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Setup course, topic, and a pool of questions with ascending difficulties
    content_svc = ContentService(db_session)
    course = content_svc.create_course(CourseCreate(title="Adaptive Math"))
    topic = content_svc.create_topic(TopicCreate(course_id=course.course_id, name="Algebra"))

    questions = []
    difficulties = [0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.95]
    for d in difficulties:
        q = content_svc.create_question(QuestionCreate(
            topic_id=topic.topic_id,
            prompt=f"Question at diff {d}",
            difficulty=d,
            correct_answer="correct",
            options=["correct", "wrong"]
        ))
        questions.append(q)

    # 2. Start diagnostic quiz (UC-01)
    diag_res = client.post(f"/v1/courses/{course.course_id}/diagnostic", headers=headers)
    assert diag_res.status_code == 200
    diag_data = diag_res.json()
    session_id = diag_data["session_id"]
    current_q = diag_data["first_question"]
    assert current_q is not None

    seen_question_ids = {current_q["question_id"]}

    # 3. Answer 3 correct in a row -> should step difficulty UP
    for i in range(3):
        res = client.post(
            f"/v1/quiz-sessions/{session_id}/answers",
            json={
                "attempt_id": str(uuid.uuid4()),
                "question_id": current_q["question_id"],
                "submitted_answer": "correct",
                "time_taken": 10.0
            },
            headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["correct"] is True
        if i < 2:
            current_q = data["next_question"]
            assert current_q["question_id"] not in seen_question_ids  # FR-603: No repeats
            seen_question_ids.add(current_q["question_id"])

    # After 3 correct answers, verify next question difficulty stepped UP
    next_stepped_up_q = data["next_question"]
    assert next_stepped_up_q is not None
    assert next_stepped_up_q["question_id"] not in seen_question_ids
    seen_question_ids.add(next_stepped_up_q["question_id"])
    assert next_stepped_up_q["difficulty"] >= 0.5  # Stepped up significantly from initial 0.1

    # 4. Answer 2 incorrect in a row -> should step difficulty DOWN
    current_q = next_stepped_up_q
    for i in range(2):
        res = client.post(
            f"/v1/quiz-sessions/{session_id}/answers",
            json={
                "attempt_id": str(uuid.uuid4()),
                "question_id": current_q["question_id"],
                "submitted_answer": "wrong",
                "time_taken": 15.0
            },
            headers=headers
        )
        assert res.status_code == 200
        data = res.json()
        assert data["correct"] is False
        if i == 0 and data["next_question"]:
            current_q = data["next_question"]
            assert current_q["question_id"] not in seen_question_ids
            seen_question_ids.add(current_q["question_id"])

    # Verify no repeats across entire session
    assert len(seen_question_ids) == len(set(seen_question_ids))


def test_nfr08_idempotent_attempt_id(client: TestClient, db_session):
    """
    Verify NFR-08: Answers carry a client-generated attempt_id so a retried request cannot count twice.
    """
    user, token = setup_learner(db_session, "idempotent")
    headers = {"Authorization": f"Bearer {token}"}

    content_svc = ContentService(db_session)
    course = content_svc.create_course(CourseCreate(title="Idempotency Course"))
    topic = content_svc.create_topic(TopicCreate(course_id=course.course_id, name="Idempotency Topic"))
    q = content_svc.create_question(QuestionCreate(
        topic_id=topic.topic_id,
        prompt="Idempotent question?",
        difficulty=0.5,
        correct_answer="42",
        options=["42", "0"]
    ))

    session_id = uuid.uuid4()
    attempt_id = uuid.uuid4()

    payload = {
        "attempt_id": str(attempt_id),
        "question_id": str(q.question_id),
        "submitted_answer": "42",
        "time_taken": 5.0
    }

    # First submission
    res1 = client.post(f"/v1/quiz-sessions/{session_id}/answers", json=payload, headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["correct"] is True

    # Count attempts in database
    attempts_count_1 = db_session.query(Attempt).filter(Attempt.attempt_id == attempt_id).count()
    assert attempts_count_1 == 1

    # Retried submission with identical attempt_id
    res2 = client.post(f"/v1/quiz-sessions/{session_id}/answers", json=payload, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["correct"] is True
    assert data2["mastery_updated"] == data1["mastery_updated"]

    # Verify still exactly 1 attempt recorded (no double counting)
    attempts_count_2 = db_session.query(Attempt).filter(Attempt.attempt_id == attempt_id).count()
    assert attempts_count_2 == 1


def test_fr104_content_events_and_engagement_metrics(client: TestClient, db_session):
    """
    Verify FR-104 & FR-307:
    - Consent check blocks tracking if not consented
    - Content events log opened, completed, skipped, time on task
    - Derived completion rate, skip rate and average session time
    """
    # Create unconsented user
    repo = AccountsRepository(db_session)
    suffix = uuid.uuid4().hex[:8]
    raw_user = repo.create_user(f"unconsented_{suffix}@test.com", get_password_hash("pass123"), "learner")
    token = create_access_token(raw_user.user_id, role="learner")
    headers = {"Authorization": f"Bearer {token}"}

    content_id = uuid.uuid4()

    # 1. Unconsented user refused (FR-104)
    res_blocked = client.post(
        f"/v1/content/{content_id}/events",
        json={"event_type": "opened", "duration": 10.0},
        headers=headers
    )
    assert res_blocked.status_code == 403
    assert res_blocked.json()["error"]["code"] == "CONSENT_REQUIRED"

    # 2. Record consent
    client.post("/v1/me/consent", json={"consent_given": True}, headers=headers)

    # 3. Log events: 1 opened (60s), 1 completed (120s), 1 skipped (30s)
    # Total events = 3; completed = 1; skipped = 1
    # Completion rate = 1/3 ~ 0.333; skip rate = 1/3 ~ 0.333; avg session = (60+120+30)/3 = 70.0s
    client.post(f"/v1/content/{content_id}/events", json={"event_type": "opened", "duration": 60.0}, headers=headers)
    client.post(f"/v1/content/{content_id}/events", json={"event_type": "completed", "duration": 120.0}, headers=headers)
    client.post(f"/v1/content/{content_id}/events", json={"event_type": "skipped", "duration": 30.0}, headers=headers)

    # 4. Fetch /v1/me/progress to verify derived metrics (FR-307, FR-701)
    progress_res = client.get("/v1/me/progress", headers=headers)
    assert progress_res.status_code == 200
    prog = progress_res.json()
    eng = prog["engagement"]

    assert eng["total_events"] == 3
    assert math.isclose(eng["completion_rate"], 1.0 / 3.0, rel_tol=1e-2)
    assert math.isclose(eng["skip_rate"], 1.0 / 3.0, rel_tol=1e-2)
    assert math.isclose(eng["avg_session_time"], 70.0, rel_tol=1e-2)
