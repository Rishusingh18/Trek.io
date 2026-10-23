"""
Accounts module comprehensive tests adhering to FR-101, FR-103, FR-104, NFR-05, NFR-06, and NFR-07.
"""
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.modules.accounts.repository import AccountsRepository
from app.db.models.knowledge import Attempt, InteractionEvent
from app.db.models.recommender import Recommendation
from app.db.models.content import Course, Topic, ContentItem, Question


def test_fr101_user_registration_and_login_flow(client: TestClient):
    """Verify FR-101: User registration and login flow."""
    reg_payload = {
        "email": "student_flow@test.com",
        "password": "ValidPassword123!",
        "role": "learner"
    }

    # 1. Register new user
    reg_res = client.post("/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    user_data = reg_res.json()
    assert user_data["email"] == reg_payload["email"]
    assert user_data["role"] == "learner"
    assert "user_id" in user_data

    # 2. Duplicate registration rejected
    dup_res = client.post("/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 400
    assert dup_res.json()["error"]["code"] == "EMAIL_EXISTS"

    # 3. Successful login returns JWT token
    login_res = client.post("/v1/auth/login", json={
        "email": reg_payload["email"],
        "password": reg_payload["password"]
    })
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 4. Access /v1/me with token
    me_res = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == reg_payload["email"]


def test_nfr06_schema_validation_rejects_invalid_inputs(client: TestClient):
    """Verify NFR-06: Request schemas reject invalid email format or weak password."""
    # Invalid email
    bad_email_res = client.post("/v1/auth/register", json={
        "email": "not-an-email",
        "password": "ValidPassword123!"
    })
    assert bad_email_res.status_code == 422
    assert bad_email_res.json()["error"]["code"] == "VALIDATION_ERROR"

    # Short password (< 6 chars)
    short_pw_res = client.post("/v1/auth/register", json={
        "email": "valid@test.com",
        "password": "123"
    })
    assert short_pw_res.status_code == 422
    assert short_pw_res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_nfr07_srs53_account_deletion_and_anonymization(client: TestClient, db_session):
    """
    Verify NFR-07 & SRS section 5.3:
    Account deletion permanently purges personal user fields while replacing learner ID
    on attempts, events and recommendations with an anonymous ID to preserve experiment data.
    """
    # 1. Register and login
    email = "delete_me@test.com"
    reg_res = client.post("/v1/auth/register", json={
        "email": email,
        "password": "Password123!",
        "role": "learner"
    })
    user_id = uuid.UUID(reg_res.json()["user_id"])

    login_res = client.post("/v1/auth/login", json={"email": email, "password": "Password123!"})
    token = login_res.json()["access_token"]

    # 2. Seed related data: Course, Topic, ContentItem, Question, Attempt, Event, Recommendation
    course = Course(course_id=uuid.uuid4(), title="Test Course")
    db_session.add(course)
    topic = Topic(topic_id=uuid.uuid4(), course_id=course.course_id, name="Test Topic")
    db_session.add(topic)
    content = ContentItem(content_id=uuid.uuid4(), topic_id=topic.topic_id, title="Item 1", type="text", difficulty=1, duration=100)
    db_session.add(content)
    question = Question(question_id=uuid.uuid4(), topic_id=topic.topic_id, prompt="Q?", difficulty=0.5, correct_answer="A")
    db_session.add(question)
    db_session.commit()

    attempt = Attempt(
        attempt_id=uuid.uuid4(),
        user_id=user_id,
        question_id=question.question_id,
        correct=True,
        time_taken=12.5,
        answered_at=datetime.now(timezone.utc)
    )
    db_session.add(attempt)

    event = InteractionEvent(
        event_id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        user_id=user_id,
        content_id=content.content_id,
        event_type="completed",
        duration=100.0
    )
    db_session.add(event)

    rec = Recommendation(
        rec_id=uuid.uuid4(),
        user_id=user_id,
        content_id=content.content_id,
        rank=1,
        reason="Strengthens a weak topic",
        shown_at=datetime.now(timezone.utc),
        outcome="accepted"
    )
    db_session.add(rec)
    db_session.commit()

    # 3. Call DELETE /v1/me
    del_res = client.delete("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["user_id"] == str(user_id)
    anonymous_id = uuid.UUID(del_data["anonymized_id"])
    assert anonymous_id != user_id

    # 4. Verify user record is completely removed from accounts table (NFR-07)
    repo = AccountsRepository(db_session)
    assert repo.get_by_id(user_id) is None
    assert repo.get_by_email(email) is None

    # 5. Verify attempt is preserved with anonymous_id (SRS 5.3)
    db_session.expire_all()
    updated_attempt = db_session.execute(select(Attempt).where(Attempt.attempt_id == attempt.attempt_id)).scalar_one()
    assert updated_attempt.user_id == anonymous_id

    # 6. Verify interaction event is preserved with anonymous_id (SRS 5.3)
    updated_event = db_session.execute(select(InteractionEvent).where(InteractionEvent.event_id == event.event_id)).scalar_one()
    assert updated_event.user_id == anonymous_id

    # 7. Verify recommendation is preserved with anonymous_id (SRS 5.3)
    updated_rec = db_session.execute(select(Recommendation).where(Recommendation.rec_id == rec.rec_id)).scalar_one()
    assert updated_rec.user_id == anonymous_id
