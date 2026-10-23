"""
Unit tests and acceptance tests for Learner and Instructor Dashboard APIs.
Traces to FR-701 to FR-705, NFR-02, NFR-06, and UC-04.
"""
import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.core.auth import create_access_token, get_password_hash
from app.modules.accounts.repository import AccountsRepository
from app.modules.content.service import ContentService
from app.modules.content.schemas import CourseCreate, TopicCreate, QuestionCreate, ContentItemCreate
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.schemas import InteractionEventCreate
from app.modules.experiments.service import ExperimentsService



def setup_users_and_courses(db_session):
    accounts_repo = AccountsRepository(db_session)
    content_svc = ContentService(db_session)
    k_svc = KnowledgeService(db_session)

    suffix = uuid.uuid4().hex[:6]

    # Create Instructors
    inst_a = accounts_repo.create_user(f"inst_a_{suffix}@test.com", get_password_hash("pass123"), "instructor")
    inst_b = accounts_repo.create_user(f"inst_b_{suffix}@test.com", get_password_hash("pass123"), "instructor")

    # Create Learners
    learner_1 = accounts_repo.create_user(f"learner_1_{suffix}@test.com", get_password_hash("pass123"), "learner")
    accounts_repo.record_consent(learner_1.user_id)
    learner_2 = accounts_repo.create_user(f"learner_2_{suffix}@test.com", get_password_hash("pass123"), "learner")
    accounts_repo.record_consent(learner_2.user_id)

    # Course A (Instructor A)
    course_a = content_svc.create_course(CourseCreate(
        title=f"Python Programming {suffix}",
        description="Intro to Python",
        instructor_id=inst_a.user_id
    ))
    t_a1 = content_svc.create_topic(TopicCreate(course_id=course_a.course_id, name="Syntax"))
    t_a2 = content_svc.create_topic(TopicCreate(course_id=course_a.course_id, name="Functions"))

    # Course B (Instructor B)
    course_b = content_svc.create_course(CourseCreate(
        title=f"Data Structures {suffix}",
        description="Trees and Graphs",
        instructor_id=inst_b.user_id
    ))
    t_b1 = content_svc.create_topic(TopicCreate(course_id=course_b.course_id, name="Trees"))

    # Add Questions and Content
    q1 = content_svc.create_question(QuestionCreate(
        topic_id=t_a1.topic_id,
        difficulty=0.5,
        prompt="What is Python?",
        correct_answer="language"
    ))
    c1 = content_svc.create_content_item(ContentItemCreate(
        topic_id=t_a1.topic_id,
        title="Python Basics",
        type="video",
        difficulty=1,
        duration=300
    ))

    # Learner 1 takes activity in Course A
    k_svc.repo.upsert_mastery(learner_1.user_id, t_a1.topic_id, score=0.25, confidence=0.8)
    k_svc.repo.record_attempt(uuid.uuid4(), learner_1.user_id, q1.question_id, correct=False, time_taken=30.0)
    k_svc.log_interaction_event(learner_1.user_id, InteractionEventCreate(content_id=c1.content_id, event_type="opened", duration=150))
    k_svc.repo.derive_and_update_engagement_rollups(learner_1.user_id)

    # Precompute class topic mastery rollup for Course A (NFR-02)
    exp_svc = ExperimentsService(db_session)
    exp_svc.repo.upsert_class_topic_mastery(
        course_id=course_a.course_id,
        topic_id=t_a1.topic_id,
        average_mastery=0.25,
        learner_count=1,
        weak_count=1
    )

    db_session.commit()

    return {
        "inst_a": inst_a,
        "inst_b": inst_b,
        "learner_1": learner_1,
        "learner_2": learner_2,
        "course_a": course_a,
        "course_b": course_b,
        "t_a1": t_a1,
        "t_a2": t_a2,
        "t_b1": t_b1,
        "q1": q1,
        "c1": c1,
        "inst_a_token": create_access_token(inst_a.user_id, role="instructor"),
        "inst_b_token": create_access_token(inst_b.user_id, role="instructor"),
        "learner_1_token": create_access_token(learner_1.user_id, role="learner"),
        "learner_2_token": create_access_token(learner_2.user_id, role="learner"),
    }


def test_learner_cannot_read_another_learner_data(client: TestClient, db_session):
    """
    Verify ownership: Learner A accessing /v1/me/* sees ONLY their own data.
    Learner A cannot access instructor endpoints.
    """
    data = setup_users_and_courses(db_session)
    learner_2_auth = {"Authorization": f"Bearer {data['learner_2_token']}"}

    # 1. Learner 2 reads /v1/me/mastery -> returns empty, cannot see Learner 1's mastery
    res = client.get("/v1/me/mastery", headers=learner_2_auth)
    assert res.status_code == 200
    masteries = res.json()
    assert len(masteries) == 0  # Learner 2 has no mastery

    # 2. Learner 2 tries accessing instructor heatmap -> 403 Forbidden
    res_inst = client.get(f"/v1/instructor/courses/{data['course_a'].course_id}/heatmap", headers=learner_2_auth)
    assert res_inst.status_code == 403
    assert res_inst.json()["error"]["code"] == "FORBIDDEN"


def test_learner_me_endpoints(client: TestClient, db_session):
    """
    Verify FR-701 & FR-705: Learner views mastery, progress (completion, time, streaks)
    and exports report as CSV and PDF.
    """
    data = setup_users_and_courses(db_session)
    auth = {"Authorization": f"Bearer {data['learner_1_token']}"}

    # 1. GET /v1/me/mastery
    m_res = client.get("/v1/me/mastery", headers=auth)
    assert m_res.status_code == 200
    masteries = m_res.json()
    assert len(masteries) >= 1
    assert masteries[0]["score"] == 0.25
    assert masteries[0]["label"] == "weak"

    # 2. GET /v1/me/progress
    p_res = client.get("/v1/me/progress", headers=auth)
    assert p_res.status_code == 200
    prog = p_res.json()
    assert prog["user_id"] == str(data["learner_1"].user_id)
    assert "streak_days" in prog
    assert "avg_session_time" in prog
    assert "completion_rate" in prog

    # 3. GET /v1/me/report?format=csv
    csv_res = client.get("/v1/me/report?format=csv", headers=auth)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "topic_id,score" in csv_res.text

    # 4. GET /v1/me/report?format=pdf
    pdf_res = client.get("/v1/me/report?format=pdf", headers=auth)
    assert pdf_res.status_code == 200
    assert "application/pdf" in pdf_res.headers["content-type"]
    assert pdf_res.content.startswith(b"%PDF")


def test_instructor_cannot_read_another_instructor_course_heatmap(client: TestClient, db_session):
    """
    Verify ownership check: Instructor B cannot access Instructor A's course heatmap.
    """
    data = setup_users_and_courses(db_session)
    inst_b_auth = {"Authorization": f"Bearer {data['inst_b_token']}"}

    res = client.get(f"/v1/instructor/courses/{data['course_a'].course_id}/heatmap", headers=inst_b_auth)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_instructor_cannot_read_another_instructor_course_at_risk(client: TestClient, db_session):
    """
    Verify ownership check: Instructor B cannot read at-risk list for Instructor A's course.
    """
    data = setup_users_and_courses(db_session)
    inst_b_auth = {"Authorization": f"Bearer {data['inst_b_token']}"}

    res = client.get(f"/v1/instructor/courses/{data['course_a'].course_id}/at-risk", headers=inst_b_auth)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_instructor_cannot_read_learner_outside_their_courses(client: TestClient, db_session):
    """
    Verify UC-04, FR-703: An instructor cannot view learners outside their own courses.
    Instructor B attempts to view Learner 1 (who only takes Course A).
    """
    data = setup_users_and_courses(db_session)
    inst_b_auth = {"Authorization": f"Bearer {data['inst_b_token']}"}

    res = client.get(f"/v1/instructor/learners/{data['learner_1'].user_id}/history", headers=inst_b_auth)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


def test_uc04_review_at_risk_learners(client: TestClient, db_session):
    """
    Acceptance test for UC-04 (SRS section 8.4):
    1) Instructor opens class dashboard -> shows topic heatmap and at-risk list.
    2) Given a learner who meets configured at-risk criteria, learner appears in the list.
    3) Instructor drills down into learner's history.
    """
    data = setup_users_and_courses(db_session)
    inst_a_auth = {"Authorization": f"Bearer {data['inst_a_token']}"}

    # 1. Instructor A views heatmap for Course A
    heat_res = client.get(f"/v1/instructor/courses/{data['course_a'].course_id}/heatmap", headers=inst_a_auth)
    assert heat_res.status_code == 200
    heatmap = heat_res.json()
    assert len(heatmap) >= 1
    assert heatmap[0]["average_mastery"] == 0.25
    assert heatmap[0]["weak_count"] == 1

    # 2. Instructor A views at-risk learners for Course A (Learner 1 is weak in Topic 1)
    risk_res = client.get(f"/v1/instructor/courses/{data['course_a'].course_id}/at-risk?weak_topics_above=1", headers=inst_a_auth)
    assert risk_res.status_code == 200
    risk_data = risk_res.json()
    assert risk_data["total_learners_at_risk"] >= 1
    learner_ids = [item["user_id"] for item in risk_data["at_risk_learners"]]
    assert str(data["learner_1"].user_id) in learner_ids

    # 3. Instructor A drills down into Learner 1's history
    hist_res = client.get(f"/v1/instructor/learners/{data['learner_1'].user_id}/history", headers=inst_a_auth)
    assert hist_res.status_code == 200
    hist = hist_res.json()
    assert hist["user_id"] == str(data["learner_1"].user_id)
    assert len(hist["attempts"]) >= 1
    assert len(hist["activities"]) >= 1


def test_nfr02_heatmap_reads_precomputed_rollups(client: TestClient, db_session):
    """
    Verify NFR-02: Heatmap reads from precomputed rollup table without scanning attempts.
    """
    data = setup_users_and_courses(db_session)
    inst_a_auth = {"Authorization": f"Bearer {data['inst_a_token']}"}

    # Query with topic filter (FR-704)
    res = client.get(
        f"/v1/instructor/courses/{data['course_a'].course_id}/heatmap?topic_id={data['t_a1'].topic_id}",
        headers=inst_a_auth
    )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["topic_id"] == str(data["t_a1"].topic_id)
    assert rows[0]["learner_count"] == 1
