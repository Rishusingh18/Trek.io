"""
Strategy Error and Timeout Fallback Test adhering to NFR-08.
Requirement NFR-08:
"If a recommendation strategy errors or times out, the system shall catch the
error, log a warning, and fall back to the rule-based strategy instead of failing."
"""
import uuid
from typing import List
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import create_access_token, get_password_hash
from app.modules.accounts.repository import AccountsRepository
from app.modules.content.service import ContentService
from app.modules.content.schemas import CourseCreate, TopicCreate, ContentItemCreate
from app.modules.knowledge.service import KnowledgeService
from app.modules.recommender.service import RecommenderService
from app.modules.recommender.strategies import STRATEGY_REGISTRY
from app.modules.recommender.strategies.base import LearnerContext, ScoredItem


class FaultyCrashingStrategy:
    """Mock strategy that simulates an unexpected runtime exception / vector index timeout."""
    name: str = "faulty_ai_strategy"

    def score(self, ctx: LearnerContext, candidates: List) -> List[ScoredItem]:
        raise TimeoutError("Simulated external vector database timeout / connection reset")


def test_nfr08_strategy_error_falls_back_to_rule_based(client: TestClient, db_session: Session):
    """
    Verify NFR-08: When a custom or experimental strategy crashes,
    the pipeline falls back to rule-based scoring and records the fallback step.
    """
    accounts_repo = AccountsRepository(db_session)
    content_svc = ContentService(db_session)
    k_svc = KnowledgeService(db_session)

    suffix = uuid.uuid4().hex[:6]

    learner = accounts_repo.create_user(f"fallback_user_{suffix}@test.com", get_password_hash("pass123"), "learner")
    accounts_repo.record_consent(learner.user_id)
    learner_auth = {"Authorization": f"Bearer {create_access_token(learner.user_id, role='learner')}"}

    course = content_svc.create_course(CourseCreate(title=f"Fallback Course {suffix}", description="Test course"))
    topic = content_svc.create_topic(TopicCreate(course_id=course.course_id, name="Algorithms"))
    content_item = content_svc.create_content_item(ContentItemCreate(
        topic_id=topic.topic_id,
        title="Binary Search",
        type="video",
        difficulty=2,
        duration=300
    ))

    # Give learner initial mastery on the topic so normal scoring executes
    k_svc.repo.upsert_mastery(learner.user_id, topic.topic_id, score=0.60, confidence=0.8)
    db_session.commit()

    # Register faulty crashing strategy
    STRATEGY_REGISTRY["faulty_ai_strategy"] = FaultyCrashingStrategy()

    try:
        # Request recommendations using the crashing strategy
        rec_svc = RecommenderService(db_session)
        recs = rec_svc.get_recommendations(
            user_id=learner.user_id,
            course_id=course.course_id,
            limit=5,
            strategy_name="faulty_ai_strategy"
        )

        # Assertions
        assert recs is not None
        assert len(recs.items) >= 1
        assert recs.items[0].content_id == content_item.content_id

        # Verify NFR-08: Fallback to rule_based occurred gracefully
        assert recs.strategy_used == "rule_based"
        assert recs.fallback_step == "rule_based"

    finally:
        # Clean up registry
        if "faulty_ai_strategy" in STRATEGY_REGISTRY:
            del STRATEGY_REGISTRY["faulty_ai_strategy"]
