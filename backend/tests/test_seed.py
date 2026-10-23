"""
Tests for Synthetic Data Seed Script (app.db.seed).
Verifies deterministic generation, prerequisite mapping, content distributions,
learner cohorts, consent recording, dismissals, and precomputed rollups.
"""
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.seed import run_seed, clean_database
from app.db.models.accounts import User
from app.db.models.content import Course, Topic, ContentItem, Question
from app.db.models.knowledge import MasteryScore, Attempt, InteractionEvent
from app.db.models.recommender import Recommendation
from app.db.models.rollups import ClassTopicMasteryRollup, LearnerEngagementRollup


def test_seed_generation_scaled(db_session: Session):
    """
    Verify seed generator produces expected schema, relationships, and distributions.
    Uses scaled learner count (50) for fast test execution.
    """
    summary = run_seed(db_session, seed=42, num_learners=50, clean=True)

    assert summary["admin"] == "admin@techxtract.com"
    assert len(summary["instructors"]) == 2
    assert summary["topics_count"] == 8
    assert summary["content_count"] == 80
    assert summary["questions_count"] == 200
    assert summary["learners_count"] == 50

    # 1. Staff Accounts & Roles
    admin_user = db_session.execute(select(User).where(User.email == "admin@techxtract.com")).scalar_one()
    assert admin_user.role == "administrator"
    assert admin_user.password_hash is not None

    inst1 = db_session.execute(select(User).where(User.email == "instructor1@techxtract.com")).scalar_one()
    assert inst1.role == "instructor"

    inst2 = db_session.execute(select(User).where(User.email == "instructor2@techxtract.com")).scalar_one()
    assert inst2.role == "instructor"

    # 2. Courses and Prerequisite Graph
    courses = db_session.execute(select(Course)).scalars().all()
    assert len(courses) >= 2

    # Primary Course has 8 topics with prerequisites
    primary_course = next(c for c in courses if c.title == "Comprehensive Python Mastery")
    assert primary_course.instructor_id == inst1.user_id

    topics = db_session.execute(
        select(Topic).where(Topic.course_id == primary_course.course_id).order_by(Topic.created_at)
    ).scalars().all()
    assert len(topics) == 8

    # Topic 0 (Basics) has no prereqs
    assert len(topics[0].prerequisite_topic_ids) == 0
    # Topic 1 (Control Flow) requires Topic 0
    assert str(topics[0].topic_id) in topics[1].prerequisite_topic_ids
    # Topic 2 (Functions) requires Topic 1
    assert str(topics[1].topic_id) in topics[2].prerequisite_topic_ids

    # 3. Content Items (80 total, difficulties 1 to 5, balanced types)
    items = db_session.execute(select(ContentItem)).scalars().all()
    assert len(items) == 80
    difficulties = {i.difficulty for i in items}
    assert difficulties == {1, 2, 3, 4, 5}
    types = {i.type for i in items}
    assert {"video", "text", "interactive", "exercise", "quiz"}.issubset(types)

    # 4. Questions (200 total across difficulty levels 0.1 to 0.95)
    questions = db_session.execute(select(Question)).scalars().all()
    assert len(questions) == 200
    min_diff = min(q.difficulty for q in questions)
    max_diff = max(q.difficulty for q in questions)
    assert min_diff <= 0.20
    assert max_diff >= 0.85

    # 5. Learners and Consent (50 learners, consent recorded)
    learners = db_session.execute(select(User).where(User.role == "learner")).scalars().all()
    assert len(learners) == 50
    for l in learners:
        assert l.consent_at is not None

    # 6. Graded Attempts and Mastery
    attempts = db_session.execute(select(Attempt)).scalars().all()
    assert len(attempts) > 100
    has_correct = any(a.correct for a in attempts)
    has_incorrect = any(not a.correct for a in attempts)
    assert has_correct and has_incorrect

    masteries = db_session.execute(select(MasteryScore)).scalars().all()
    assert len(masteries) >= 50 * 8  # 50 learners * 8 topics
    # Verify spread of masteries across cohorts (weak < 0.40, developing, strong >= 0.80)
    has_weak = any(m.score < 0.40 for m in masteries)
    has_strong = any(m.score >= 0.80 for m in masteries)
    assert has_weak and has_strong

    # 7. Interaction Events (completed, skipped, opened)
    events = db_session.execute(select(InteractionEvent)).scalars().all()
    assert len(events) > 100
    event_types = {e.event_type for e in events}
    assert "completed" in event_types
    assert "skipped" in event_types
    assert "opened" in event_types

    # 8. Recommendations and Dismissals
    recs = db_session.execute(select(Recommendation)).scalars().all()
    assert len(recs) > 0
    dismissed = [r for r in recs if r.outcome == "dismissed"]
    assert len(dismissed) > 0

    # 9. Precomputed Rollups (NFR-02)
    topic_rollups = db_session.execute(select(ClassTopicMasteryRollup)).scalars().all()
    assert len(topic_rollups) >= 8

    engagement_rollups = db_session.execute(select(LearnerEngagementRollup)).scalars().all()
    assert len(engagement_rollups) == 50


def test_seed_re_runnable_and_deterministic(db_session: Session):
    """
    Verify seed script can be re-run cleanly with deterministic output.
    """
    summary1 = run_seed(db_session, seed=123, num_learners=20, clean=True)
    summary2 = run_seed(db_session, seed=123, num_learners=20, clean=True)

    assert summary1["learners_count"] == summary2["learners_count"]
    assert summary1["content_count"] == summary2["content_count"]
    assert summary1["questions_count"] == summary2["questions_count"]

    # Verify learner count is exactly 20 without duplicates
    learners_count = db_session.execute(
        select(func.count(User.user_id)).where(User.role == "learner")
    ).scalar()
    assert learners_count == 20
