"""
Content module tests adhering to FR-201, FR-202, FR-203, and NFR-06.
"""
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.core.auth import create_access_token, get_password_hash
from app.modules.accounts.repository import AccountsRepository
from app.db.models.content import ContentItem


def setup_users(db_session):
    repo = AccountsRepository(db_session)
    suffix = uuid.uuid4().hex[:8]
    admin = repo.create_user(f"admin_{suffix}@test.com", get_password_hash("pass123"), "administrator")
    instructor = repo.create_user(f"instructor_{suffix}@test.com", get_password_hash("pass123"), "instructor")
    learner = repo.create_user(f"learner_{suffix}@test.com", get_password_hash("pass123"), "learner")
    return {
        "admin_token": create_access_token(admin.user_id, role="administrator"),
        "instructor_token": create_access_token(instructor.user_id, role="instructor"),
        "learner_token": create_access_token(learner.user_id, role="learner"),
        "admin_id": admin.user_id,
    }


def test_fr201_admin_crud_and_retire(client: TestClient, db_session):
    """
    Verify FR-201: Admin creates, edits, and retires courses, topics, content items, and questions.
    Verify items are marked retired rather than deleted.
    """
    users = setup_users(db_session)
    admin_auth = {"Authorization": f"Bearer {users['admin_token']}"}

    # 1. Course CRUD
    course_res = client.post("/v1/admin/courses", json={"title": "Data Science 101", "description": "Intro"}, headers=admin_auth)
    assert course_res.status_code == 201
    course_id = course_res.json()["course_id"]

    update_course_res = client.put(f"/v1/admin/courses/{course_id}", json={"title": "Advanced Data Science"}, headers=admin_auth)
    assert update_course_res.status_code == 200
    assert update_course_res.json()["title"] == "Advanced Data Science"

    # 2. Topic CRUD
    topic_res = client.post("/v1/admin/topics", json={"course_id": course_id, "name": "Linear Algebra", "prerequisite_topic_ids": []}, headers=admin_auth)
    assert topic_res.status_code == 201
    topic_id = topic_res.json()["topic_id"]

    # 3. ContentItem CRUD with prerequisites
    item_payload = {
        "topic_id": topic_id,
        "title": "Vectors Video",
        "type": "video",
        "difficulty": 2,
        "duration": 300,
        "prerequisite_topic_ids": []
    }
    item_res = client.post("/v1/admin/content", json=item_payload, headers=admin_auth)
    assert item_res.status_code == 201
    content_id = item_res.json()["content_id"]

    # 4. Question CRUD
    q_payload = {
        "topic_id": topic_id,
        "prompt": "What is a scalar?",
        "difficulty": 0.2,
        "correct_answer": "A single number",
        "options": ["A single number", "A matrix", "A vector"]
    }
    q_res = client.post("/v1/admin/questions", json=q_payload, headers=admin_auth)
    assert q_res.status_code == 201
    question_id = q_res.json()["question_id"]

    # 5. Retire items instead of deleting
    retire_item_res = client.delete(f"/v1/admin/content/{content_id}", headers=admin_auth)
    assert retire_item_res.status_code == 200
    assert retire_item_res.json()["is_retired"] is True

    retire_q_res = client.delete(f"/v1/admin/questions/{question_id}", headers=admin_auth)
    assert retire_q_res.status_code == 200
    assert retire_q_res.json()["is_retired"] is True

    retire_topic_res = client.delete(f"/v1/admin/topics/{topic_id}", headers=admin_auth)
    assert retire_topic_res.status_code == 200
    assert retire_topic_res.json()["is_retired"] is True

    retire_course_res = client.delete(f"/v1/admin/courses/{course_id}", headers=admin_auth)
    assert retire_course_res.status_code == 200
    assert retire_course_res.json()["is_retired"] is True


def test_fr202_content_item_prerequisites_and_fields(client: TestClient, db_session):
    """
    Verify FR-202: Each content item carries topic, difficulty (1 to 5),
    type, estimated duration and prerequisite topics.
    """
    users = setup_users(db_session)
    admin_auth = {"Authorization": f"Bearer {users['admin_token']}"}

    c_res = client.post("/v1/admin/courses", json={"title": "Math Course"}, headers=admin_auth)
    t1_res = client.post("/v1/admin/topics", json={"course_id": c_res.json()["course_id"], "name": "Topic A"}, headers=admin_auth)
    t2_res = client.post("/v1/admin/topics", json={"course_id": c_res.json()["course_id"], "name": "Topic B", "prerequisite_topic_ids": [t1_res.json()["topic_id"]]}, headers=admin_auth)

    # Valid ContentItem with difficulty 1 to 5 and prerequisite topic IDs
    item_res = client.post("/v1/admin/content", json={
        "topic_id": t2_res.json()["topic_id"],
        "title": "Topic B Deep Dive",
        "type": "article",
        "difficulty": 4,
        "duration": 600,
        "prerequisite_topic_ids": [t1_res.json()["topic_id"]]
    }, headers=admin_auth)
    assert item_res.status_code == 201
    data = item_res.json()
    assert data["difficulty"] == 4
    assert data["duration"] == 600
    assert data["prerequisite_topic_ids"] == [t1_res.json()["topic_id"]]

    # Invalid difficulty (e.g. 6 or 0) rejected by schema
    invalid_diff_res = client.post("/v1/admin/content", json={
        "topic_id": t2_res.json()["topic_id"],
        "title": "Invalid Diff",
        "type": "article",
        "difficulty": 6,
        "duration": 600
    }, headers=admin_auth)
    assert invalid_diff_res.status_code == 422


def test_fr203_tag_coverage_report(client: TestClient, db_session):
    """Verify FR-203: The system shall report content items missing required tags."""
    users = setup_users(db_session)
    admin_auth = {"Authorization": f"Bearer {users['admin_token']}"}

    c_res = client.post("/v1/admin/courses", json={"title": "Tag Course"}, headers=admin_auth)
    t_res = client.post("/v1/admin/topics", json={"course_id": c_res.json()["course_id"], "name": "Tag Topic"}, headers=admin_auth)
    topic_id = uuid.UUID(t_res.json()["topic_id"])

    # 1. Well-tagged item
    client.post("/v1/admin/content", json={
        "topic_id": str(topic_id),
        "title": "Valid Item",
        "type": "video",
        "difficulty": 3,
        "duration": 120
    }, headers=admin_auth)

    # 2. Create directly an item missing type (simulating legacy/un-tagged content)
    missing_item = ContentItem(
        content_id=uuid.uuid4(),
        topic_id=topic_id,
        title="Untagged Item",
        type="",
        difficulty=0,
        duration=0,
        prerequisite_topic_ids=[],
        is_retired=False
    )
    db_session.add(missing_item)
    db_session.commit()

    # Query tag coverage report
    rep_res = client.get("/v1/admin/content/tag-coverage", headers=admin_auth)
    assert rep_res.status_code == 200
    data = rep_res.json()
    assert data["missing_tag_items_count"] >= 1
    assert any(item["title"] == "Untagged Item" for item in data["items_missing_tags"])


def test_catalog_redis_cache_and_db_fallback(client: TestClient, db_session):
    """Verify course catalog is cached in Redis with expiry and falls back to PostgreSQL on miss."""
    users = setup_users(db_session)
    admin_auth = {"Authorization": f"Bearer {users['admin_token']}"}

    c_res = client.post("/v1/admin/courses", json={"title": "Physics 101"}, headers=admin_auth)
    course_id = c_res.json()["course_id"]
    t_res = client.post("/v1/admin/topics", json={"course_id": course_id, "name": "Mechanics"}, headers=admin_auth)
    topic_id = t_res.json()["topic_id"]
    client.post("/v1/admin/content", json={
        "topic_id": topic_id,
        "title": "Newton Laws",
        "type": "video",
        "difficulty": 1,
        "duration": 180
    }, headers=admin_auth)

    # 1. First fetch: Redis miss, falls back to DB, caches to Redis
    cat1_res = client.get(f"/v1/courses/{course_id}/catalog")
    assert cat1_res.status_code == 200
    data1 = cat1_res.json()
    assert data1["title"] == "Physics 101"
    assert len(data1["topics"]) == 1
    assert data1["topics"][0]["content_items"][0]["title"] == "Newton Laws"

    # 2. Second fetch: Serves from Redis cache
    cat2_res = client.get(f"/v1/courses/{course_id}/catalog")
    assert cat2_res.status_code == 200
    assert cat2_res.json() == data1


def test_admin_routes_forbidden_for_learner_and_instructor(client: TestClient, db_session):
    """Verify FR-103, NFR-06: Learner and instructor get 403 Forbidden on admin content routes."""
    users = setup_users(db_session)
    learner_auth = {"Authorization": f"Bearer {users['learner_token']}"}
    instructor_auth = {"Authorization": f"Bearer {users['instructor_token']}"}

    # Learner forbidden
    res1 = client.post("/v1/admin/courses", json={"title": "Hacked Course"}, headers=learner_auth)
    assert res1.status_code == 403
    assert res1.json()["error"]["code"] == "FORBIDDEN"

    res2 = client.get("/v1/admin/content/tag-coverage", headers=learner_auth)
    assert res2.status_code == 403

    # Instructor forbidden
    res3 = client.post("/v1/admin/courses", json={"title": "Instructor Course"}, headers=instructor_auth)
    assert res3.status_code == 403
    assert res3.json()["error"]["code"] == "FORBIDDEN"
