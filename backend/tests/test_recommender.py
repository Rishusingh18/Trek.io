"""
Unit tests and acceptance tests for the Recommender Module.
Traces to FR-501 to FR-510, NFR-01, NFR-08, NFR-11, and UC-02.
"""
import uuid
from fastapi.testclient import TestClient

from app.core.auth import create_access_token, get_password_hash
from app.modules.accounts.repository import AccountsRepository
from app.modules.content.service import ContentService
from app.modules.content.schemas import CourseCreate, TopicCreate, ContentItemCreate
from app.modules.knowledge.service import KnowledgeService
from app.modules.knowledge.schemas import InteractionEventCreate
from app.modules.recommender.service import RecommenderService
from app.modules.recommender.strategies import STRATEGY_REGISTRY, RuleBasedStrategy
from app.modules.recommender.strategies.base import LearnerContext


def setup_course_and_topics(db_session):
    content_svc = ContentService(db_session)
    suffix = uuid.uuid4().hex[:6]

    course = content_svc.create_course(CourseCreate(title=f"Math Course {suffix}", description="Test course"))

    # Topic 1: Algebra (no prereqs)
    t1 = content_svc.create_topic(TopicCreate(course_id=course.course_id, name="Algebra", prerequisite_topic_ids=[]))
    # Topic 2: Calculus (prereq: Algebra)
    t2 = content_svc.create_topic(TopicCreate(course_id=course.course_id, name="Calculus", prerequisite_topic_ids=[str(t1.topic_id)]))

    # Content items for Algebra
    c1 = content_svc.create_content_item(ContentItemCreate(
        topic_id=t1.topic_id,
        title="Algebra Basics",
        type="video",
        difficulty=1,
        duration=180,
        prerequisite_topic_ids=[]
    ))
    c2 = content_svc.create_content_item(ContentItemCreate(
        topic_id=t1.topic_id,
        title="Algebra Advanced",
        type="article",
        difficulty=3,
        duration=300,
        prerequisite_topic_ids=[]
    ))

    # Content items for Calculus
    c3 = content_svc.create_content_item(ContentItemCreate(
        topic_id=t2.topic_id,
        title="Calculus Intro",
        type="video",
        difficulty=2,
        duration=240,
        prerequisite_topic_ids=[str(t1.topic_id)]
    ))
    c4 = content_svc.create_content_item(ContentItemCreate(
        topic_id=t2.topic_id,
        title="Derivatives Deep Dive",
        type="article",
        difficulty=4,
        duration=400,
        prerequisite_topic_ids=[str(t1.topic_id)]
    ))

    return {
        "course": course,
        "t1": t1,
        "t2": t2,
        "c1": c1,
        "c2": c2,
        "c3": c3,
        "c4": c4,
    }


def setup_learner(db_session, email_prefix: str = "rec_learner", consent: bool = True):
    repo = AccountsRepository(db_session)
    suffix = uuid.uuid4().hex[:8]
    user = repo.create_user(f"{email_prefix}_{suffix}@test.com", get_password_hash("pass123"), "learner")
    if consent:
        repo.record_consent(user.user_id)
    token = create_access_token(user.user_id, role="learner")
    return user, token


def test_fr502_completed_items_dropped_unless_weak_topic(client: TestClient, db_session):
    """
    Verify FR-502: The system shall not recommend items already completed,
    unless a review is due for a weak topic.
    """
    data = setup_course_and_topics(db_session)
    user, token = setup_learner(db_session, "fr502")
    auth = {"Authorization": f"Bearer {token}"}
    k_svc = KnowledgeService(db_session)

    # 1. Learner completes c1 (Algebra Basics) and c3 (Calculus Intro)
    k_svc.log_interaction_event(user.user_id, InteractionEventCreate(content_id=data["c1"].content_id, event_type="completed", duration=180))
    k_svc.log_interaction_event(user.user_id, InteractionEventCreate(content_id=data["c3"].content_id, event_type="completed", duration=240))

    # Set Algebra (t1) mastery to weak (0.25) -> c1 is eligible for review!
    k_svc.repo.upsert_mastery(user.user_id, data["t1"].topic_id, score=0.25, confidence=0.8)
    # Set Calculus (t2) mastery to strong (0.85) -> c3 should be DROPPED
    k_svc.repo.upsert_mastery(user.user_id, data["t2"].topic_id, score=0.85, confidence=0.8)
    db_session.commit()

    res = client.get(f"/v1/courses/{data['course'].course_id}/recommendations", headers=auth)
    assert res.status_code == 200
    returned_cids = {item["content_id"] for item in res.json()["items"]}

    # c1 (completed in weak topic) is retained for review
    assert str(data["c1"].content_id) in returned_cids
    # c3 (completed in strong topic) is dropped
    assert str(data["c3"].content_id) not in returned_cids


def test_fr503_weak_prerequisites_dropped(client: TestClient, db_session):
    """
    Verify FR-503: The system shall not recommend an item whose prerequisite topics are still weak.
    """
    data = setup_course_and_topics(db_session)
    user, token = setup_learner(db_session, "fr503")
    auth = {"Authorization": f"Bearer {token}"}
    k_svc = KnowledgeService(db_session)

    # Set Topic 1 (Algebra) to weak mastery 0.20
    k_svc.repo.upsert_mastery(user.user_id, data["t1"].topic_id, score=0.20, confidence=0.8)
    db_session.commit()

    res = client.get(f"/v1/courses/{data['course'].course_id}/recommendations", headers=auth)
    assert res.status_code == 200
    returned_cids = {item["content_id"] for item in res.json()["items"]}

    # Items for Calculus (c3, c4 require Algebra) must be dropped
    assert str(data["c3"].content_id) not in returned_cids
    assert str(data["c4"].content_id) not in returned_cids
    # Items for Algebra itself (no prereqs) can be recommended
    assert str(data["c1"].content_id) in returned_cids


def test_fr509_dismissed_items_dropped_during_quiet_period(client: TestClient, db_session):
    """
    Verify FR-509: Learner dismisses an item; system does not re-suggest it during quiet period.
    """
    data = setup_course_and_topics(db_session)
    user, token = setup_learner(db_session, "fr509")
    auth = {"Authorization": f"Bearer {token}"}
    k_svc = KnowledgeService(db_session)

    # Initialize mastery
    k_svc.repo.upsert_mastery(user.user_id, data["t1"].topic_id, score=0.60, confidence=0.8)
    db_session.commit()

    # Initial recommendation
    res1 = client.get(f"/v1/courses/{data['course'].course_id}/recommendations", headers=auth)
    assert res1.status_code == 200
    first_item = res1.json()["items"][0]
    rec_id = first_item["rec_id"]
    content_id = first_item["content_id"]

    # Dismiss the item
    dismiss_res = client.post(f"/v1/recommendations/{rec_id}/dismiss", headers=auth)
    assert dismiss_res.status_code == 200
    assert dismiss_res.json()["status"] == "dismissed"

    # Subsequent recommendation must not include the dismissed item
    res2 = client.get(f"/v1/courses/{data['course'].course_id}/recommendations", headers=auth)
    assert res2.status_code == 200
    subsequent_cids = [item["content_id"] for item in res2.json()["items"]]
    assert content_id not in subsequent_cids


def test_fr504_rule_based_scoring_formula_and_dominant_factor(client: TestClient, db_session):
    """
    Verify FR-504, SRS section 7.2:
    S(i) = w1*gap + w2*fit + w3*ready + w4*eng
    Identifies dominant term and sets appropriate reason.
    """
    data = setup_course_and_topics(db_session)
    user, _ = setup_learner(db_session, "fr504")

    # Set up LearnerContext directly for unit test
    t1_id = data["t1"].topic_id
    ctx = LearnerContext(
        user_id=user.user_id,
        mastery_map={t1_id: 0.10},  # Large gap = 0.90
        completed_item_ids=set(),
        dismissed_item_ids=set(),
        weights={"w1": 0.4, "w2": 0.3, "w3": 0.2, "w4": 0.1},
        overall_completion_rate=0.5,
        stretch=0.10
    )

    strategy = RuleBasedStrategy()
    candidates = [data["c1"]]  # difficulty 1
    scored = strategy.score(ctx, candidates)
    assert len(scored) == 1

    item = scored[0]
    # gap = 0.90 -> w1*gap = 0.36
    # fit: diff norm = 0.0, target = 0.20 -> fit = 0.80 -> w2*fit = 0.24
    # ready: 1.0 -> w3*ready = 0.20
    # eng: 0.5 -> w4*eng = 0.05
    # Total = 0.36 + 0.24 + 0.20 + 0.05 = 0.85
    assert abs(item.score - 0.85) < 1e-3
    assert item.dominant_factor == "gap"
    assert item.reason == "Strengthens a weak topic"


def test_fr505_nfr11_explainable_reasons_and_templates(client: TestClient, db_session):
    """
    Verify FR-505 & NFR-11: Every recommendation shows a one-line readable reason.
    Admin can customize templates.
    """
    data = setup_course_and_topics(db_session)
    user, token = setup_learner(db_session, "fr505")
    auth = {"Authorization": f"Bearer {token}"}
    k_svc = KnowledgeService(db_session)

    # Set topic mastery to weak (0.2) so gap dominates
    k_svc.repo.upsert_mastery(user.user_id, data["t1"].topic_id, score=0.20, confidence=0.8)
    db_session.commit()

    res = client.get(f"/v1/courses/{data['course'].course_id}/recommendations", headers=auth)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) > 0

    for item in items:
        assert "reason" in item
        assert len(item["reason"]) > 5
        assert isinstance(item["rank"], int)


def test_nfr08_strategy_error_falls_back_to_rule_based(client: TestClient, db_session):
    """
    Verify NFR-08: If the assigned strategy errors (e.g. NotImplementedError),
    the pipeline falls back to rule-based strategy and records fallback_step.
    """
    data = setup_course_and_topics(db_session)
    user, token = setup_learner(db_session, "nfr08")
    auth = {"Authorization": f"Bearer {token}"}
    k_svc = KnowledgeService(db_session)

    # Set mastery
    k_svc.repo.upsert_mastery(user.user_id, data["t1"].topic_id, score=0.50, confidence=0.8)
    db_session.commit()

    # Call with explicitly requested strategy that throws NotImplementedError
    svc = RecommenderService(db_session)
    rec_list = svc.get_recommendations(
        user_id=user.user_id,
        course_id=data["course"].course_id,
        strategy_name="embeddings"  # Raises NotImplementedError
    )

    # Fallback to rule_based occurred cleanly
    assert rec_list.strategy_used == "rule_based"
    assert rec_list.fallback_step == "rule_based"
    assert len(rec_list.items) > 0


def test_fr510_cold_start_fallback_chain_and_step_recording(client: TestClient, db_session):
    """
    Verify FR-510: A learner with no mastery history falls back to entry-level items,
    and fallback_step is recorded in response for experiment traffic exclusion.
    """
    data = setup_course_and_topics(db_session)
    user, token = setup_learner(db_session, "fr510_cold")
    auth = {"Authorization": f"Bearer {token}"}

    # No mastery scores inserted
    res = client.get(f"/v1/courses/{data['course'].course_id}/recommendations", headers=auth)
    assert res.status_code == 200
    data_out = res.json()

    assert data_out["fallback_step"] == "entry_level"
    assert len(data_out["items"]) > 0
    # Entry-level item difficulty is 1
    first_item = data_out["items"][0]
    assert first_item["difficulty"] == 1
    assert "Entry-level" in first_item["reason"]


def test_uc02_follow_recommended_path_acceptance(client: TestClient, db_session):
    """
    Acceptance test for UC-02 (SRS section 8.2):
    Given weak topic T, when the learner requests recommendations,
    then the list includes items for T, excludes items with weak prerequisites,
    and each item shows a reason.
    """
    data = setup_course_and_topics(db_session)
    user, token = setup_learner(db_session, "uc02")
    auth = {"Authorization": f"Bearer {token}"}
    k_svc = KnowledgeService(db_session)

    # Topic 1 (Algebra) is weak (0.25).
    # Calculus requires Algebra, so Calculus items must be excluded.
    # Topic 1 items must be included with one-line reasons.
    k_svc.repo.upsert_mastery(user.user_id, data["t1"].topic_id, score=0.25, confidence=0.8)
    db_session.commit()

    res = client.get(f"/v1/courses/{data['course'].course_id}/recommendations", headers=auth)
    assert res.status_code == 200
    resp_data = res.json()

    items = resp_data["items"]
    assert len(items) > 0

    # 1. Includes items for weak topic (Algebra)
    algebra_items = [i for i in items if i["topic_id"] == str(data["t1"].topic_id)]
    assert len(algebra_items) > 0

    # 2. Excludes items whose prerequisites are weak (Calculus items)
    calculus_items = [i for i in items if i["topic_id"] == str(data["t2"].topic_id)]
    assert len(calculus_items) == 0

    # 3. Each item has a reason
    for item in items:
        assert item["reason"] != ""
        assert item["rank"] >= 1


def test_fr104_recommendations_refused_without_consent(client: TestClient, db_session):
    """
    Verify FR-104 & NFR-07: Tracking endpoints refuse requests until learner records consent.
    """
    data = setup_course_and_topics(db_session)
    user, token = setup_learner(db_session, "no_consent", consent=False)
    auth = {"Authorization": f"Bearer {token}"}

    res = client.get(f"/v1/courses/{data['course'].course_id}/recommendations", headers=auth)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "CONSENT_REQUIRED"
