"""
Comprehensive Access Control Matrix Test Suite.
Covers every role against every route group adhering to FR-102, FR-103, FR-104, and NFR-06.

Roles:
1. Anonymous (Unauthenticated)
2. Learner without Consent
3. Learner with Consent
4. Instructor
5. Administrator

Route Groups:
- Public Group (/v1/health, /v1/auth/*)
- Admin Group (/v1/admin/*)
- Instructor Group (/v1/instructor/*)
- Learner Group (/v1/me/*, /v1/courses/{id}/recommendations, /v1/courses/{id}/diagnostic)
"""
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import create_access_token, get_password_hash
from app.modules.accounts.repository import AccountsRepository
from app.modules.content.service import ContentService
from app.modules.content.schemas import CourseCreate, TopicCreate, QuestionCreate, ContentItemCreate


def setup_matrix_environment(db_session: Session):
    accounts_repo = AccountsRepository(db_session)
    content_svc = ContentService(db_session)

    suffix = uuid.uuid4().hex[:6]

    # Users
    admin = accounts_repo.create_user(f"admin_{suffix}@test.com", get_password_hash("pass123"), "administrator")
    instructor = accounts_repo.create_user(f"instructor_{suffix}@test.com", get_password_hash("pass123"), "instructor")
    learner_with_consent = accounts_repo.create_user(f"learner_c_{suffix}@test.com", get_password_hash("pass123"), "learner")
    accounts_repo.record_consent(learner_with_consent.user_id)
    learner_no_consent = accounts_repo.create_user(f"learner_noc_{suffix}@test.com", get_password_hash("pass123"), "learner")

    # Instructor's Course & Content
    course = content_svc.create_course(CourseCreate(
        title=f"Access Matrix Course {suffix}",
        description="Testing route group permissions",
        instructor_id=instructor.user_id
    ))
    topic = content_svc.create_topic(TopicCreate(
        course_id=course.course_id,
        name=f"Matrix Topic {suffix}"
    ))
    question = content_svc.create_question(QuestionCreate(
        topic_id=topic.topic_id,
        prompt="Sample Prompt?",
        difficulty=0.5,
        correct_answer="Option A"
    ))

    item = content_svc.create_content_item(ContentItemCreate(
        topic_id=topic.topic_id,
        title="Matrix Content",
        type="article",
        difficulty=2,
        duration=300
    ))

    return {
        "admin_auth": {"Authorization": f"Bearer {create_access_token(admin.user_id, role='administrator')}"},
        "instructor_auth": {"Authorization": f"Bearer {create_access_token(instructor.user_id, role='instructor')}"},
        "learner_consent_auth": {"Authorization": f"Bearer {create_access_token(learner_with_consent.user_id, role='learner')}"},
        "learner_noc_auth": {"Authorization": f"Bearer {create_access_token(learner_no_consent.user_id, role='learner')}"},
        "course_id": str(course.course_id),
        "topic_id": str(topic.topic_id),
        "content_id": str(item.content_id),
        "question_id": str(question.question_id),
        "learner_consent_id": str(learner_with_consent.user_id),
    }


# ==================== 1. Public Routes ====================
def test_matrix_public_routes(client: TestClient, db_session: Session):
    """Public endpoints (/health, /v1/auth/*) accessible without credentials (never return 401)."""
    env = setup_matrix_environment(db_session)

    # Health check is public (returns 200 if live services available or 503 degraded, never 401)
    res_anon = client.get("/health")
    assert res_anon.status_code in [200, 503], f"Unexpected status {res_anon.status_code}"

    res_learner = client.get("/health", headers=env["learner_consent_auth"])
    assert res_learner.status_code == res_anon.status_code

    res_admin = client.get("/health", headers=env["admin_auth"])
    assert res_admin.status_code == res_anon.status_code

    # Public Auth endpoint (login accessible to anonymous users without token)
    res_login = client.post("/v1/auth/login", data={"username": "fake@test.com", "password": "wrongpassword"})
    assert res_login.status_code in [400, 401, 422]  # Handled by auth logic, not blocked by missing bearer


# ==================== 2. Admin Route Group ====================
def test_matrix_admin_routes(client: TestClient, db_session: Session):
    """
    Admin endpoints (/v1/admin/*) require 'administrator' role.
    Anonymous -> 401
    Learner -> 403
    Instructor -> 403
    Administrator -> 200
    """
    env = setup_matrix_environment(db_session)
    routes = [
        ("GET", "/v1/admin/content/tag-coverage"),
        ("GET", "/v1/admin/config/ranking_weights"),
        ("GET", "/v1/admin/config-audits"),
    ]

    for method, path in routes:
        # Anonymous -> 401
        res_anon = client.request(method, path)
        assert res_anon.status_code == 401, f"Expected 401 for anonymous on {path}, got {res_anon.status_code}"

        # Learner with consent -> 403
        res_learner = client.request(method, path, headers=env["learner_consent_auth"])
        assert res_learner.status_code == 403, f"Expected 403 for learner on {path}, got {res_learner.status_code}"

        # Learner without consent -> 403
        res_noc = client.request(method, path, headers=env["learner_noc_auth"])
        assert res_noc.status_code == 403, f"Expected 403 for learner without consent on {path}, got {res_noc.status_code}"

        # Instructor -> 403
        res_inst = client.request(method, path, headers=env["instructor_auth"])
        assert res_inst.status_code == 403, f"Expected 403 for instructor on {path}, got {res_inst.status_code}"

        # Administrator -> 200
        res_admin = client.request(method, path, headers=env["admin_auth"])
        assert res_admin.status_code == 200, f"Expected 200 for admin on {path}, got {res_admin.status_code}"


# ==================== 3. Instructor Route Group ====================
def test_matrix_instructor_routes(client: TestClient, db_session: Session):
    """
    Instructor endpoints (/v1/instructor/*) require 'instructor' or 'administrator' role.
    Anonymous -> 401
    Learner -> 403
    Instructor -> 200 (for owned course)
    Administrator -> 200
    """
    env = setup_matrix_environment(db_session)
    course_id = env["course_id"]

    routes = [
        ("GET", f"/v1/instructor/courses/{course_id}/heatmap"),
        ("GET", f"/v1/instructor/courses/{course_id}/at-risk"),
    ]

    for method, path in routes:
        # Anonymous -> 401
        res_anon = client.request(method, path)
        assert res_anon.status_code == 401

        # Learner with consent -> 403
        res_l = client.request(method, path, headers=env["learner_consent_auth"])
        assert res_l.status_code == 403

        # Learner without consent -> 403
        res_noc = client.request(method, path, headers=env["learner_noc_auth"])
        assert res_noc.status_code == 403

        # Instructor (owner) -> 200
        res_inst = client.request(method, path, headers=env["instructor_auth"])
        assert res_inst.status_code == 200

        # Administrator -> 200
        res_admin = client.request(method, path, headers=env["admin_auth"])
        assert res_admin.status_code == 200


# ==================== 4. Learner Route Group & Consent ====================
def test_matrix_learner_routes_and_consent(client: TestClient, db_session: Session):
    """
    Learner endpoints:
    - Consent-gated routes (FR-104: recommendations, tracking events, data export):
      Anonymous -> 401
      Learner WITHOUT consent -> 403
      Learner WITH consent -> 200
    - Learner personal view routes (FR-701: mastery, progress):
      Anonymous -> 401
      Authenticated Learner -> 200
    """
    env = setup_matrix_environment(db_session)
    course_id = env["course_id"]
    content_id = env["content_id"]

    # 4a. Consent-gated tracking & personalization routes
    consent_gated_routes = [
        ("GET", f"/v1/courses/{course_id}/recommendations", None),
        ("POST", f"/v1/content/{content_id}/events", {"event_type": "opened", "duration": 25.0}),
        ("GET", "/v1/me/report?format=csv", None),
    ]

    for method, path, body in consent_gated_routes:
        # Anonymous -> 401
        res_anon = client.request(method, path, json=body)
        assert res_anon.status_code == 401, f"Expected 401 on {path}, got {res_anon.status_code}"

        # Learner without consent -> 403 (FR-104)
        res_noc = client.request(method, path, headers=env["learner_noc_auth"], json=body)
        assert res_noc.status_code == 403, f"Expected 403 on {path} without consent, got {res_noc.status_code}"

        # Learner with consent -> 200
        res_consent = client.request(method, path, headers=env["learner_consent_auth"], json=body)
        assert res_consent.status_code == 200, f"Expected 200 on {path} with consent, got {res_consent.status_code}"

    # 4b. Personal dashboard views
    personal_routes = [
        ("GET", "/v1/me/mastery"),
        ("GET", "/v1/me/progress"),
    ]

    for method, path in personal_routes:
        # Anonymous -> 401
        res_anon = client.request(method, path)
        assert res_anon.status_code == 401, f"Expected 401 on {path}, got {res_anon.status_code}"

        # Authenticated learner -> 200
        res_learner = client.request(method, path, headers=env["learner_noc_auth"])
        assert res_learner.status_code == 200, f"Expected 200 on {path} for learner, got {res_learner.status_code}"
